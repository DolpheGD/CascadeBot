const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');
const Tool = require('../../models/Tool');
const { trackQuestProgress } = require('../../commands/utility/quest.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('mine')
        .setDescription('Mine for resources'),

    async execute(interaction) {
        let cooldown = 15 * 1000; // 20 seconds cooldown
        const userId = interaction.user.id;

        try {
            await interaction.deferReply();

            // Find or create the user
            const [user] = await User.findOrCreate({
                where: { discordId: userId },
                defaults: { username: interaction.user.username }
            });

            // Find or create the inventory for the user
            const [inventory] = await Inventory.findOrCreate({
                where: { userId: user.id },
                defaults: { wood: 0, stone: 0, palmLeaves: 0, gold: 0, copper: 0 }
            });

            // Find the user's tools
            const tool = await Tool.findOne({ where: { userId: user.id } });

            const lastMine = user.lastMine || 0;
            const now = Date.now();

            let hasPickaxe = tool?.metalPickaxe && tool.metalPickaxeDurability > 0;
            if (hasPickaxe){
                cooldown = 5 * 1000; // 13 seconds cooldown
            }

            if (now - lastMine < cooldown) {
                return interaction.editReply({
                    content: `You are mining too fast! Please wait ${Math.ceil((cooldown - (now - lastMine)) / 1000)} more seconds.`,
                    ephemeral: true
                });
            }

            let stone, goldChance, bonusStoneChance, copperChance, hugeCopperVeinChance;
            let titleSuffix = hasPickaxe ? ' [⛏️]' : '';

            if (hasPickaxe) {
                stone = Math.floor(Math.random() * 5) + 2; // 2-6 stone
                goldChance = 0.18; // 18% chance for gold
                bonusStoneChance = 0.42; // 42% chance for bonus stone
                copperChance = 0.37; // 37% chance for copper
                hugeCopperVeinChance = 0.14; // 14 chance for huge copper vein

                // Decrease pickaxe durability
                tool.metalPickaxeDurability -= 1;
                if (tool.metalPickaxeDurability === 0) {
                    tool.metalPickaxe = false;
                }
                await tool.save();
            } else {
                stone = Math.floor(Math.random() * 3) + 2; // 2-4 stone
                goldChance = 0.04; // 4% chance for gold
                bonusStoneChance = 0.25; // 25% chance for bonus stone
                copperChance = 0.2; // 20% chance for copper
                hugeCopperVeinChance = 0.04; // 4% chance for huge copper vein
            }
            
            // chances
            let gold = Math.random() < goldChance ? 1 : 0;
            let bonusStone = Math.random() < bonusStoneChance ? Math.floor(Math.random() * 3) + 2 : 0; // 2-4 bonus stone
            let copper = Math.random() < copperChance ? Math.floor(Math.random() * 3) + 1 : 0; // 1-3 copper
            let hugeCopperVein = Math.random() < hugeCopperVeinChance ? Math.floor(Math.random() * 4) + 5 : 0; // 5-8 huge copper vein
            let hugeGoldVein = 0;
            let bonusruby = 0;

            // Pickaxe chances
            if (hasPickaxe) {
                if (Math.random() < 0.03) { // 3% chance for huge gold vein
                    hugeGoldVein = Math.floor(Math.random() * 6) + 4 ; // 4-9 gold
                }
                if (Math.random() < 0.02) { // 2% chance for rubies
                    bonusruby = Math.floor(Math.random() * 2) + 1 ; // 1-2 rubies
                }
            }

            const thieves = ['JD', 'JC23GDFFMI', 'Nesjonat', 'VRT Gaming', 'Aizer', 'Rohan', 'Josh', 'Dolphe', 'Tbnr', 'Bio', 'Verx', 'Doggy', 'NF89', 'Triv', 'Rex', 'Duko', 'Arkiver', 'Caliper'];
            const thiefName = thieves[Math.floor(Math.random() * thieves.length)]; // Randomly select a thief's name
            const thiefName2 = thieves.filter(t => t !== thiefName)[Math.floor(Math.random() * (thieves.length - 1))];

            // Negative events
            const negativeEventChance = Math.random();
            if (negativeEventChance < 0.1) { // 10% chance for negative events
                if (Math.random() < 0.6 && inventory.stone > 3) { // 60% chance to lose stone
                    const stoneLost = Math.floor(Math.random() * 3) + 1;
                    inventory.stone = Math.max(inventory.stone - stoneLost, 0);
                    await inventory.save();

                    const embed = new EmbedBuilder()
                        .setColor('#ff0000')
                        .setTitle('Failure!')
                        .setThumbnail(interaction.user.displayAvatarURL())
                        .setDescription(`You bump into ${thiefName} in the mines and they steal some stone from you!\n**-${stoneLost}** 🪨`)
                        .setFooter({ text: `Total stone: ${inventory.stone}` });

                    return interaction.editReply({content: '', embeds: [embed] });

                } else if (Math.random() < 0.5 && inventory.gold > 1) { // 20% chance to lose gold
                    const goldLost = Math.floor(Math.random() * 2) + 1;
                    inventory.gold = Math.max(inventory.gold - goldLost, 0);
                    await inventory.save();

                    const embed = new EmbedBuilder()
                        .setColor('#ff0000')
                        .setTitle('Failure!')
                        .setThumbnail(interaction.user.displayAvatarURL())
                        .setDescription(`You find ${thiefName}, who is jealous of your gold and attacks you!\n**-${goldLost}** ✨`)
                        .setFooter({ text: `Total gold: ${inventory.gold}` });

                    return interaction.editReply({content: '', embeds: [embed] });
                } else if (Math.random() < 0.4) { // 20% chance for the new event
                    if (inventory.wood > 0 || inventory.palmLeaves > 0 || inventory.stone > 0 || inventory.copper > 0) {
                        inventory.wood = Math.max(inventory.wood - 1, 0);
                        inventory.palmLeaves = Math.max(inventory.palmLeaves - 1, 0);
                        inventory.stone = Math.max(inventory.stone - 1, 0);
                        inventory.copper = Math.max(inventory.copper - 1, 0);
                        await inventory.save();

                        const embed = new EmbedBuilder()
                            .setColor('#ff0000')
                            .setTitle('Failure!')
                            .setThumbnail(interaction.user.displayAvatarURL())
                            .setDescription(`You, ${thiefName}, and ${thiefName2} got into a scuffle at the mines!\n**-1** 🪵, **-1** 🌿, **-1** 🪨, **-1** 🔶`)
                            .setFooter({ text: `Resources left: Wood: ${inventory.wood}, Palm Leaves: ${inventory.palmLeaves}, Stone: ${inventory.stone}, Copper: ${inventory.copper}` });

                        return interaction.editReply({content: '', embeds: [embed] });
                    } else { // Default message if the user doesn't have enough resources
                        const embed = new EmbedBuilder()
                            .setColor('#ff0000')
                            .setTitle('Failure!')
                            .setThumbnail(interaction.user.displayAvatarURL())
                            .setDescription(`${thiefName} saw you at the mines and laughed at how poor you were!`);

                        return interaction.editReply({content: '', embeds: [embed] });
                    }
                }
            }

            // Update inventory with mined resources
            inventory.stone += stone + bonusStone;
            inventory.gold += gold + hugeGoldVein;
            inventory.copper += copper + hugeCopperVein;
            inventory.ruby += bonusruby;
            user.lastMine = now;

            // Save inventory and user cooldown
            await inventory.save();
            await user.save();

            const embed = new EmbedBuilder()
                .setColor('#00ff00')
                .setTitle('Success!' + titleSuffix)
                .setThumbnail(interaction.user.displayAvatarURL())
                .setDescription(`You mined some stone!\n**+${stone}**🪨`)
                .setFooter({ text: `Total stone: ${inventory.stone}` });

            if (bonusStone > 0) {
                embed.addFields({ name: 'Bonus!', value: `You mined extra stone!\n**+${bonusStone}**🪨`, inline: false });
            }

            if (copper > 0) {
                embed.addFields({ name: 'Bonus!', value: `You mined some copper!\n**+${copper}**🔶`, inline: false });
            }

            if (gold > 0) {
                embed.addFields({ name: '〈Rare Bonus!〉', value: `You mined something shiny!\n**+${gold}**✨`, inline: false });
            }

            if (hugeCopperVein > 0) {
                embed.addFields({ name: '〈Rare Bonus!〉', value: `You struck a huge copper vein!\n**+${hugeCopperVein}**🔶`, inline: false });
            }

            if (hugeGoldVein > 0) {
                    embed.addFields({ name: '【✨ULTRA RARE BONUS!✨】', value: `You found a huge gold vein!\n**+${hugeGoldVein}**✨`, inline: false });
            }
            
            if (bonusruby > 0) {
                    embed.addFields({ name: '【♦️ULTRA RARE BONUS!♦️】', value: `You found some rare rubies!\n**+${bonusruby}**♦️`, inline: false });
            }

            if (hasPickaxe && tool.metalPickaxeDurability === 0) {
                embed.addFields({ name: '**Pickaxe Broken!**', value: 'Your pickaxe has broken!', inline: false });
            }

            await interaction.editReply({content: '', embeds: [embed] });

                        // Success mining -> progress updates
                        const questResult = await trackQuestProgress(interaction.user.id, 'mine', interaction); 

                        // Send quest result message if there are quest updates
                        if (questResult != 'No active quest found.') {
                            const questEmbed = new EmbedBuilder()
                                .setTitle('Quest Update')
                                .setDescription(questResult)
                                .setThumbnail(interaction.user.displayAvatarURL({ dynamic: true }))
                                .setColor('#00ff00');
                            return interaction.followUp({content: '', embeds: [questEmbed] });
                        }
                        return;
        } catch (error) {
            console.error('Error mining:', error);
            return interaction.reply({ content: 'An error occurred while mining. Please try again later.', ephemeral: true });
        }
    },
};
