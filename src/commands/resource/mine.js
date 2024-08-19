const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');
const Tool = require('../../models/Tool');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('mine')
        .setDescription('Mine for resources'),

    async execute(interaction) {
        let cooldown = 25 * 1000; // 25 seconds cooldown
        const userId = interaction.user.id;

        try {
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
                cooldown = 13 * 1000; // 13 seconds cooldown
            }

            if (now - lastMine < cooldown) {
                return interaction.reply({
                    content: `You are mining too fast! Please wait ${Math.ceil((cooldown - (now - lastMine)) / 1000)} more seconds.`,
                    ephemeral: true
                });
            }

            let stone, goldChance, bonusStoneChance, copperChance, hugeCopperVeinChance;
            let titleSuffix = hasPickaxe ? ' [⛏️]' : '';

            if (hasPickaxe) {
                stone = Math.floor(Math.random() * 5) + 2; // 2-6 stone
                goldChance = 0.16; // 16% chance for gold
                bonusStoneChance = 0.45; // 45% chance for bonus stone
                copperChance = 0.35; // 35% chance for copper
                hugeCopperVeinChance = 0.10; // 10% chance for huge copper vein

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
                hugeCopperVeinChance = 0.03; // 3% chance for huge copper vein
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
                if (Math.random() < 0.02) { // 2% chance for huge gold vein
                    hugeGoldVein = Math.floor(Math.random() * 6) + 4 ; // 4-9 gold
                }
                if (Math.random() < 0.01) { // 1% chance for rubies
                    bonusruby = Math.floor(Math.random() * 2) + 1 ; // 1-2 rubies
                }
            }

            // Negative events (unchanged)
            const negativeEventChance = Math.random();
            if (negativeEventChance < 0.1) { // 10% chance for negative events
                if (inventory.stone > 3 && Math.random() < 0.8) { // 80% of the negative events being stone theft
                    const stoneLost = Math.floor(Math.random() * 3) + 1;
                    inventory.stone = Math.max(inventory.stone - stoneLost, 0);
                    await inventory.save();

                    const embed = new EmbedBuilder()
                        .setColor('#ff0000')
                        .setTitle('Failure!')
                        .setDescription(`You bump into Josh in the mines and he steals some stone from you!\n**-${stoneLost}** 🪨`)
                        .setFooter({ text: `Total stone: ${inventory.stone}` });

                    return interaction.reply({ embeds: [embed] });
                } else if (inventory.gold > 1) { // The other 20% of negative events being gold theft
                    const goldLost = Math.floor(Math.random() * 2) + 1;
                    inventory.gold = Math.max(inventory.gold - goldLost, 0);
                    await inventory.save();

                    const embed = new EmbedBuilder()
                        .setColor('#ff0000')
                        .setTitle('Failure!')
                        .setDescription(`You find Rohan, who is jealous of your gold and attacks you!\n**-${goldLost}** ✨`)
                        .setFooter({ text: `Total gold: ${inventory.gold}` });

                    return interaction.reply({ embeds: [embed] });
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
                .setDescription(`You obtained ${stone} 🪨`)
                .setFooter({ text: `Total stone: ${inventory.stone}` });

            if (bonusStone > 0) {
                embed.addFields({ name: 'Bonus!', value: `You mined extra stone!\n**+${bonusStone}** 🪨`, inline: false });
            }

            if (copper > 0) {
                embed.addFields({ name: 'Bonus!', value: `You mined some copper!\n**+${copper}** 🔶`, inline: false });
            }

            if (gold > 0) {
                embed.addFields({ name: 'Rare Bonus!', value: `You mined something shiny!\n**+${gold}** ✨`, inline: false });
            }

            if (hugeCopperVein > 0) {
                embed.addFields({ name: 'Rare Bonus!', value: `You struck a huge copper vein!\n**+${hugeCopperVein}** 🔶`, inline: false });
            }

            if (hugeGoldVein > 0) {
                    embed.addFields({ name: '✨ULTRA RARE BONUS!✨', value: `You found a huge gold vein!\n**+${ultraRareBonus.amount}** ✨`, inline: false });
            }
            
            if (bonusruby > 0) {
                    embed.addFields({ name: '♦️ULTRA RARE BONUS!♦️', value: `You found some rare rubies!\n**+${ultraRareBonus.amount}** ♦️`, inline: false });
            }

            if (hasPickaxe && tool.metalPickaxeDurability === 0) {
                embed.addFields({ name: '**Pickaxe Broken!**', value: ``, inline: false });
            }

            return interaction.reply({ embeds: [embed] });
        } catch (error) {
            console.error('Error mining:', error);
            return interaction.reply({ content: 'An error occurred while mining. Please try again later.', ephemeral: true });
        }
    },
};
