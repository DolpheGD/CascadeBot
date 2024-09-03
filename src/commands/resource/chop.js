const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');
const Tool = require('../../models/Tool'); // Import Tool model
const { trackQuestProgress } = require('../../commands/utility/quest.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('chop')
        .setDescription('Chop wood'),

    async execute(interaction) {
        let cooldown = 15 * 1000; // 15 seconds cooldown
        try{
            await interaction.reply('Processing chop...');
            const userId = interaction.user.id;
            const username = interaction.user.username;
            
            // Create or find the user and ensure the username is set
            const [user] = await User.findOrCreate({
                where: { discordId: userId },
                defaults: { username: username }
            });

            // Create or find the inventory
            const [inventory] = await Inventory.findOrCreate({
                where: { userId: user.id },
                defaults: { wood: 0, stone: 0, palmLeaves: 0, gold: 0, rope: 0 }
            });

            // Find the user's tools
            const tool = await Tool.findOne({ where: { userId: user.id } });

            const hasAxe = tool && tool.metalAxe && tool.metalAxeDurability > 0;

            if (hasAxe) {
                cooldown = 5 * 1000; // 8 seconds cooldown
            }

            const lastChop = user.lastChop || 0;
            const now = Date.now();

            if (now - lastChop < cooldown) {
                return interaction.editReply({
                    content: `You are chopping too fast! Please wait ${Math.ceil((cooldown - (now - lastChop)) / 1000)} more seconds.`,
                    ephemeral: true
                });
            }

            let wood = hasAxe ? Math.floor(Math.random() * 5) + 3 : Math.floor(Math.random() * 5) + 1;
            inventory.wood += wood;

            let isNegative = false;
            let isBonus = false;
            let bonusWood = 0;
            let extraBonusWood = 0;
            let stolenWood = 0;
            let stolenLeaves = 0;
            let palmLeaves = 0;
            let rope = 0;
            let bonusApple = 0;

            if (hasAxe) { // check for axe durability
                tool.metalAxeDurability -= 1;

                if (tool.metalAxeDurability <= 0) {
                    tool.metalAxe = false; // The axe breaks if durability reaches 0
                    tool.metalAxeDurability = 0;
                }
                await tool.save();
            }

            const thieves = ['JD', 'JC23GDFFMI', 'Nesjonat', 'VRT Gaming', 'Aizer', 'Rohan', 'Josh', 'Dolphe', 'Tbnr', 'Bio', 'Verx', 'Doggy', 'NF89', 'Triv', 'Rex', 'Duko', 'Arkiver', 'Caliper'];
            const thiefName = thieves[Math.floor(Math.random() * thieves.length)]; // Randomly select a thief's name

            const isJoshEvent = Math.random() < 0.5;
            if (Math.random() < 0.1 && inventory.palmLeaves > 0 && inventory.wood > 0) { // negative event 10%
                isNegative = true;

                if (isJoshEvent) { // wood-stealing event
                    if (hasAxe) {
                        tool.metalAxeDurability -= 1;
                        if (tool.metalAxeDurability <= 0) {
                            tool.metalAxe = false; // The axe breaks if durability reaches 0
                            tool.metalAxeDurability = 0;
                        }
                        bonusWood = 4;
                        rope = 1;
                        inventory.wood += bonusWood;
                        inventory.rope += rope;
                        await tool.save();
                    } else {
                        stolenWood = Math.floor(Math.random() * 3) + 1;
                        inventory.wood -= Math.min(inventory.wood, stolenWood);
                    }
                } else { // leaf-stealing event
                    if (hasAxe) {
                        tool.metalAxeDurability -= 1;
                        if (tool.metalAxeDurability <= 0) {
                            tool.metalAxe = false; // The axe breaks if durability reaches 0
                            tool.metalAxeDurability = 0;
                        }
                        palmLeaves = 4;
                        rope = 1;
                        inventory.wood += bonusWood;
                        inventory.palmLeaves += palmLeaves;
                        await tool.save();
                    } else {
                        stolenLeaves = Math.floor(Math.random() * 5) + 1;
                        inventory.palmLeaves -= Math.min(inventory.palmLeaves, stolenLeaves);
                    }
                }
            } else {
                // extra stuff from axe
                if (Math.random() < (hasAxe ? 0.4 : 0.15)) {
                    isBonus = true;
                    bonusWood = Math.floor(Math.random() * (hasAxe ? 5 : 3)) + 4;
                    inventory.wood += bonusWood;
                }
                if (Math.random() < (hasAxe ? 0.7 : 0.5)) {
                    palmLeaves = Math.floor(Math.random() * 4) + 1;
                    inventory.palmLeaves += palmLeaves;
                }
                if (Math.random() < (hasAxe ? 0.2 : 0.05)) {
                    rope += 1;
                    inventory.rope += rope;
                }
                if (Math.random() < (hasAxe ? 0.2 : 0.1)) {
                    bonusApple += 1;
                    inventory.apples += bonusApple;
                }
                if (hasAxe && Math.random() < 0.03) {
                    extraBonusWood = Math.floor(Math.random() * 16) + 15;
                    inventory.wood += extraBonusWood;
                }
                
            }

            // Save the tool, inventory, and user data
            user.lastChop = now;
            await inventory.save();
            await user.save();

            const embed = new EmbedBuilder()
                .setColor(isNegative ? '#ff0000' : '#00ff00')
                .setThumbnail(interaction.user.displayAvatarURL()) // Add the user's avatar as a thumbnail
                .setTitle(
                    (isNegative ? 'Failure!' : 'Success!') + (hasAxe ? ' [🪓]' : '')
                )
                .setFooter({ text: `Total wood: ${inventory.wood}` });

            if (isNegative){
                if (isJoshEvent){
                    if (hasAxe){ // wood 
                        embed.setDescription(`${thiefName} tried to steal your wood, but you fended them off! **+4🪵** and **+1🪢**\n🪓 -1 durability`)
                    }
                    else{
                        embed.setDescription(`${thiefName} stole your wood while you were chopping!\n-**${stolenWood}**🪵`)
                    }
                }
                else{ // Leaf event
                    if (hasAxe){
                        embed.setDescription(`${thiefName} tried to steal your leaves, but you fended them off! **+4🍃** and **+1🪢**\n🪓 -1 durability`)
                    }
                    else{
                        embed.setDescription(`${thiefName} stole your leaves while you weren't looking!\n-**${stolenLeaves}🍃**`)
                    }
                }
                return interaction.editReply({content: '', embeds: [embed] }); // skip bonus if negative. This is to avoid the palm leaf bonus showing up cause 
            }
            else
            {
                embed.setDescription(`You chopped some wood!\n+**${wood}🪵**`)
            }

            if (isBonus) {
                embed.addFields({ name: '**Bonus!**', value: `You chopped down a huge tree! **+${bonusWood}**🪵!`, inline: false });
            }

            if (palmLeaves > 0) {
                embed.addFields({ name: '**Bonus!**', value: `You picked up some huge leaves! **+${palmLeaves}**🍃!`, inline: false });
            }

            if (bonusApple > 0) {
                embed.addFields({ name: '**Bonus!**', value: `You plucked an apple! **+${bonusApple}**🍎!`, inline: false });
            }

            if (rope > 0) {
                embed.addFields({ name: '**〈Rare Bonus!〉**', value: `You found some leftover rope! **+${rope}**🪢!`, inline: false });
            }

            if (hasAxe && extraBonusWood > 0) {
                embed.addFields({ name: '**【🌳ULTRA Rare Bonus!🌳】**', value: `You chopped down a humongous tree! **+${extraBonusWood}**🪵!`, inline: false });
            }

            if (hasAxe && tool.metalAxeDurability === 0) {
                embed.addFields({ name: '**Axe Broken!**', value: `Your axe has broken!`, inline: false });
            }

            await interaction.editReply({content: '', embeds: [embed] });

                        // Success chopping -> progress updates
                        const questResult = await trackQuestProgress(interaction.user.id, 'chop', interaction); 

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
            console.error(error);
            return interaction.editReply({ content: 'There was an error while executing the command.', ephemeral: true });
        }
    },
};
