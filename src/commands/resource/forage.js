const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');
const Tool = require('../../models/Tool');
const { trackQuestProgress } = require('../../commands/utility/quest.js');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('forage')
        .setDescription('Forage for items'),

    async execute(interaction) {
        const discordId = interaction.user.id;

        try {
            await interaction.reply('Processing forage...');
            
            // Fetch the user data
            const user = await User.findOne({ where: { discordId } });

            if (!user) {
                return interaction.editReply({ content: 'User not found.', ephemeral: true });
            }

            // Check cooldown
            const now = Date.now();
            const cooldown = 20 * 1000; // 20 seconds
            if (now - user.lastForage < cooldown) {
                const secondsLeft = Math.ceil((cooldown - (now - user.lastForage)) / 1000);
                return interaction.editReply({ content: `You need to wait ${secondsLeft} seconds before foraging again.`, ephemeral: true });
            }

            // Update last forage time
            user.lastForage = now;
            await user.save();

            // Fetch or create the user's inventory
            let inventory = await Inventory.findOne({ where: { userId: user.id } });
            if (!inventory) {
                inventory = await Inventory.create({ userId: user.id });
            }

            // Fetch the user's tools
            let tools = await Tool.findOne({ where: { userId: user.id } });
            if (!tools) {
                tools = await Tool.create({ userId: user.id });
            }
            
            // Negative event (10% chance)
            if (Math.random() < 0.1) {
                const thieves = ['JD', 'JC23GDFFMI', 'Nesjonat', 'VRT Gaming', 'Aizer', 'Rohan', 'Josh', 'Dolphe', 'Tbnr', 'Bio', 'Verx', 'Doggy', 'NF89', 'Triv', 'Rex', 'Duko', 'Arkiver', 'Caliper'];

                const thief = thieves[Math.floor(Math.random() * thieves.length)];
                const thief2 = thieves.filter(t => t !== thief)[Math.floor(Math.random() * (thieves.length - 1))];
                let negativeEvent = '';
                
                const eventType = Math.random();
                
                if (eventType < 0.33) { // 33% chance to lose fruit
                    const fruits = [
                        { type: 'berries', emoji: '🫐', amount: 2 },
                        { type: 'apples', emoji: '🍎', amount: 1 },
                        { type: 'watermelon', emoji: '🍉', amount: 1 }
                    ];
                    const availableFruits = fruits.filter(f => inventory[f.type] > 0);
                
                    if (availableFruits.length > 0) {
                        const fruit = availableFruits[Math.floor(Math.random() * availableFruits.length)];
                        inventory[fruit.type] -= fruit.amount;
                        negativeEvent = `${thief} was hungry and stole your fruit! **-${fruit.amount}** ${fruit.emoji}`;
                    } else {
                        negativeEvent = `${thief} was hungry, but you had no fruit to steal!`;
                    }
                } else if (eventType < 0.66) { // 33% chance to lose general resources
                    const resources = [
                        { type: 'wood', emoji: '🪵', amount: 2 },
                        { type: 'stone', emoji: '🪨', amount: 2 },
                        { type: 'copper', emoji: '🔶', amount: 2 },
                        { type: 'palmLeaves', emoji: '🌿', amount: 2 }
                    ];
                    const availableResources = resources.filter(r => inventory[r.type] > 0);
                
                    if (availableResources.length > 0) {
                        const resource = availableResources[Math.floor(Math.random() * availableResources.length)];
                        inventory[resource.type] -= resource.amount;
                        negativeEvent = `${thief} and ${thief2} looted your items while you weren't looking! **-${resource.amount}** ${resource.emoji}`;
                    } else {
                        negativeEvent = `${thief} and ${thief2} planned to rob you, but you had no valuable resources!`;
                    }
                } else { // 33% chance to lose gold
                    if (inventory.gold > 0) {
                        inventory.gold -= 1;
                        negativeEvent = `${thief} and ${thief2} launched a surprise attack on you and stole your gold! **-1** ✨`;
                    } else {
                        inventory.wood += 1;
                        negativeEvent = `${thief} thought about robbing you, but you were too poor! ${thief} gives you wood out of pity. **+1** 🪵`;
                    }
                }
                
                // Save the negative event updates to inventory
                await inventory.save();

                // Construct the embed for the negative event
                const embed = new EmbedBuilder()
                    .setTitle('Forage Result')
                    .setDescription(`**Negative Event**\n${negativeEvent}`)
                    .setThumbnail(interaction.user.displayAvatarURL({ dynamic: true }))
                    .setColor('#ff0000');

                // Reply with the negative event result
                return interaction.editReply({content: '', embeds: [embed] });
            }

            // If no negative event, proceed with foraging logic
            let resultMessage = '';
            let bonuses = {
                normal: [],
                rare: [],
                ultraRare: []
            };

            // 50% chance for palm leaves (1-4)
            if (Math.random() < 0.5) {
                const palmLeavesAmount = Math.floor(Math.random() * 4) + 1;
                inventory.palmLeaves += palmLeavesAmount;
                resultMessage += `You found some palm leaves!\n**+${palmLeavesAmount}** 🌿\n`;
            }
            // 50% chance for berries (1-4)
            else {
                const berriesAmount = Math.floor(Math.random() * 4) + 1;
                inventory.berries += berriesAmount;
                resultMessage += `You found some berries!\n**+${berriesAmount}** 🫐\n`;
            }

            // Bonuses
            let bonusChance = Math.random();
            if (bonusChance < 0.3) { // 30% chance to get 1-3 apples
                const applesAmount = Math.floor(Math.random() * 3) + 1;
                inventory.apples += applesAmount;
                bonuses.normal.push(`**+${applesAmount}** 🍎`);
            }

            bonusChance = Math.random();
            if (bonusChance < 0.06) { // 6% chance to get 1 watermelon
                inventory.watermelon += 1;
                bonuses.rare.push(`**+1** 🍉`);
            }

            bonusChance = Math.random();
            if (bonusChance < 0.08) { // 8% chance to get 1 rope
                inventory.rope += 1;
                bonuses.rare.push(`**+1** 🪢`);
            }

            bonusChance = Math.random();
            if (bonusChance < 0.2) { // 20% chance to find 1-2 stone
                const stoneAmount = Math.floor(Math.random() * 2) + 1;
                inventory.stone += stoneAmount;
                bonuses.normal.push(`**+${stoneAmount}** 🪨`);
            }
            
            bonusChance = Math.random();
            // Tool bonuses
            if (bonusChance < 0.002 && !tools.pickaxe) { // 0.2% chance to find a pickaxe
                const pickaxeDurability = Math.floor(Math.random() * 6) + 5; // 5 to 10 durability
                tools.metalPickaxe = true;
                tools.metalPickaxeDurability = pickaxeDurability;
                bonuses.ultraRare.push(`You found a pickaxe with **${pickaxeDurability}** durability! ⛏️`);
            }
            if (bonusChance < 0.004 && bonusChance >= 0.002 && !tools.axe) { // 0.2% chance to find an axe
                const axeDurability = Math.floor(Math.random() * 6) + 5; // 5 to 10 durability
                tools.metalAxe = true;
                tools.metalAxeDurability = axeDurability;
                bonuses.ultraRare.push(`You found an axe with **${axeDurability}** durability! 🪓`);
            }
            if (bonusChance < 0.005 && bonusChance >= 0.004 && !tools.fishingRod) { // 0.1% chance to find a fishing rod
                const fishingRodDurability = Math.floor(Math.random() * 6) + 5; // 5 to 10 durability
                tools.fishingRod = true;
                tools.fishingRodDurability = fishingRodDurability;
                bonuses.ultraRare.push(`You found a fishing rod with **${fishingRodDurability}** durability! 🎣`);
            }

            // Save inventory and tools updates
            await inventory.save();
            await tools.save();

            // Construct the embed for the forage result
            const embed = new EmbedBuilder()
                .setTitle('Forage Result')
                .setDescription(resultMessage)
                .setThumbnail(interaction.user.displayAvatarURL({ dynamic: true }))
                .setColor('#00ff00');

            // Add bonus fields based on rarity
            if (bonuses.normal.length > 0) {
                embed.addFields({ name: 'Bonus!', value: bonuses.normal.join('\n'), inline: false });
            }
            if (bonuses.rare.length > 0) {
                embed.addFields({ name: '〈Rare Bonus!〉', value: bonuses.rare.join('\n'), inline: false });
            }
            if (bonuses.ultraRare.length > 0) {
                embed.addFields({ name: '【🛠️ULTRA RARE BONUS!🛠️】', value: bonuses.ultraRare.join('\n'), inline: false });
            }

            // Reply with the forage result
            await interaction.editReply({content: '', embeds: [embed] });

            // Success foraging -> progress updates
            const questResult = await trackQuestProgress(interaction.user.id, 'forage', interaction); 

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
