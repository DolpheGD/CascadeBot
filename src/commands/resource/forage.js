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
            await interaction.deferReply();
            
            // Fetch the user data
            const user = await User.findOne({ where: { discordId } });

            if (!user) {
                return interaction.editReply({ content: 'User not found.', ephemeral: true });
            }

            // Fetch the user's tools
            let tools = await Tool.findOne({ where: { userId: user.id } });
            if (!tools) {
                tools = await Tool.create({ userId: user.id });
            }

            // Check cooldown
            const now = Date.now();
            const baseCooldown = tools.gloves ? 7 * 1000 : 15 * 1000; // Glove reduces cooldown to 7 seconds
            if (now - user.lastForage < baseCooldown) {
                const secondsLeft = Math.ceil((baseCooldown - (now - user.lastForage)) / 1000);
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
            
            // Negative event (8% chance)
            if (Math.random() < 0.08) {
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


            //---------------------------------------------------------
            // Foraging Logic with Glove Modifiers
            let resultMessage = '';
            let bonuses = {
                normal: [],
                rare: [],
                ultraRare: []
            };

            // Palm leaves and berries chance - can get both with glove
            if (tools.gloves) {
                const palmLeavesAmount = Math.floor(Math.random() * 5) + 2; // 2-6 with glove
                inventory.palmLeaves += palmLeavesAmount;
                resultMessage += `You found some palm leaves!\n**+${palmLeavesAmount}** 🌿\n`;

                const berriesAmount = Math.floor(Math.random() * 5) + 2; // 2-6 with glove
                inventory.berries += berriesAmount;
                resultMessage += `You found some berries!\n**+${berriesAmount}** 🫐\n`;
            } else {
                // Without glove, it's 50% chance for either palm leaves or berries
                if (Math.random() < 0.5) {
                    const palmLeavesAmount = Math.floor(Math.random() * 4) + 1; // 1-4 without glove
                    inventory.palmLeaves += palmLeavesAmount;
                    resultMessage += `You found some palm leaves!\n**+${palmLeavesAmount}** 🌿\n`;
                } else {
                    const berriesAmount = Math.floor(Math.random() * 4) + 1; // 1-4 without glove
                    inventory.berries += berriesAmount;
                    resultMessage += `You found some berries!\n**+${berriesAmount}** 🫐\n`;
                }
            }

            // Bonuses with adjusted chances if the user has a glove
            let bonusChance = Math.random();

            if (tools.gloves && bonusChance < 0.8) { // 80% chance for apples (1-5 with glove)
                const applesAmount = Math.floor(Math.random() * 5) + 1;
                inventory.apples += applesAmount;
                bonuses.normal.push(`You found some apples! **+${applesAmount}** 🍎`);
            } else if (bonusChance < 0.3) { // 30% chance without glove
                const applesAmount = Math.floor(Math.random() * 3) + 1;
                inventory.apples += applesAmount;
                bonuses.normal.push(`You found some apples! **+${applesAmount}** 🍎`);
            }

            bonusChance = Math.random();
            if (tools.gloves && bonusChance < 0.5) { // 50% chance for watermelon (1-2 with glove)
                const watermelonAmount = Math.floor(Math.random() * 2) + 1;
                inventory.watermelon += watermelonAmount;
                bonuses.rare.push(`You found some watermelon! **+${watermelonAmount}** 🍉`);
            } else if (bonusChance < 0.09) { // 9% chance without glove
                inventory.watermelon += 1;
                bonuses.rare.push(`You found some watermelon! **+1** 🍉`);
            }

            bonusChance = Math.random();
            if (tools.gloves && bonusChance < 0.5) { // 50% chance for rope (1-2 with glove)
                const ropeAmount = Math.floor(Math.random() * 2) + 1;
                inventory.rope += ropeAmount;
                bonuses.rare.push(`You found some hidden rope! **+${ropeAmount}** 🪢`);
            } else if (bonusChance < 0.08) { // 8% chance without glove
                inventory.rope += 1;
                bonuses.rare.push(`You found some hidden rope! **+1** 🪢`);
            }

            bonusChance = Math.random();
            if (tools.gloves && bonusChance < 0.08) { // 8% chance for banana with glove
                inventory.banana += 1;
                bonuses.rare.push(`You found a banana! **+1** 🍌`);
            } else if (bonusChance < 0.01) { // 1% chance without glove
                inventory.banana += 1;
                bonuses.rare.push(`You found a banana! **+1** 🍌`);
            }

            bonusChance = Math.random();
            if (tools.gloves && bonusChance < 0.5) { // 50% chance for stone with glove
                const stoneAmount = Math.floor(Math.random() * 3) + 1;
                inventory.stone += stoneAmount;
                bonuses.normal.push(`You found some stone! **+${stoneAmount}** 🪨`);
            } else if (bonusChance < 0.2) { // 20% chance without glove
                const stoneAmount = Math.floor(Math.random() * 2) + 1;
                inventory.stone += stoneAmount;
                bonuses.normal.push(`You found some stone! **+${stoneAmount}** 🪨`);
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
                embed.addFields({ name: '【ULTRA RARE BONUS!】', value: bonuses.ultraRare.join('\n'), inline: false });
            }

            // Check if gloves are equipped
        if (tools.gloves) {
            embed.setTitle('Forage Result [🧤]')
            tools.glovesDurability -= 1;

            // Check if gloves break
            if (tools.glovesDurability <= 0) {
                tools.gloves = false;
                tools.glovesDurability = 0;
                resultMessage += `Your gloves have broken! 🧤\n`;
            }

            // Save the tool updates after reducing durability
            await tools.save();
        }

        // Continue with other forage logic...


            // Reply with the forage result
            await interaction.editReply({ content: '', embeds: [embed] });

            // Success foraging -> progress updates
            const questResult = await trackQuestProgress(interaction.user.id, 'forage', interaction);

            // Send quest result message if there are quest updates
            if (questResult !== 'No active quest found.') {
                const questEmbed = new EmbedBuilder()
                    .setTitle('Quest Update')
                    .setDescription(questResult)
                    .setThumbnail(interaction.user.displayAvatarURL({ dynamic: true }))
                    .setColor('#ffff00');
                await interaction.followUp({ embeds: [questEmbed] });
            }
            return;

        } catch (error) {
            console.error(error);
            return interaction.editReply({ content: 'There was an error while executing the command.', ephemeral: true });
        }
    },
};
