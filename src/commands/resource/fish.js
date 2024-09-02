const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');
const Tool = require('../../models/Tool');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('fish')
        .setDescription('Fish for items'),
        
    async execute(interaction) {
        const discordId = interaction.user.id;

        try {
            // Fetch the user data
            const user = await User.findOne({ where: { discordId } });

            if (!user) {
                return interaction.reply({ content: 'User not found.', ephemeral: true });
            }

            // Fetch the user's tools
            let tools = await Tool.findOne({ where: { userId: user.id } });

            if (!tools) {
                tools = await Tool.create({ userId: user.id });
            }

            if (!tools.fishingRod) {
                return interaction.reply({ content: 'You do not own a fishing rod.', ephemeral: true });
            }

            // Check cooldown
            const now = Date.now();
            const cooldown = 30 * 1000; // 30 seconds
            if (now - user.lastFish < cooldown) {
                const secondsLeft = Math.ceil((cooldown - (now - user.lastFish)) / 1000);
                return interaction.reply({ content: `You need to wait ${secondsLeft} seconds before fishing again.`, ephemeral: true });
            }

            // Update last fish time
            user.lastFish = now;
            await user.save();

            // Decrease fishing rod durability
            tools.fishingRodDurability -= 1;
            if (tools.fishingRodDurability <= 0) {
                tools.fishingRod = null; // Remove fishing rod if durability is 0
                tools.fishingRodDurability = 0;
                await tools.save();
                return interaction.reply({ content: 'Your fishing rod has broken!', ephemeral: true });
            }
            await tools.save();

            // Fetch or create the user's inventory
            let inventory = await Inventory.findOne({ where: { userId: user.id } });
            if (!inventory) {
                inventory = await Inventory.create({ userId: user.id });
            }

            // Determine fishing result
            const chance = Math.random();
            let isFail = false;
            let resultMessage = '';
            const bonuses = [];
            const thieves = ['JD', 'JC23GDFFMI', 'Nesjonat', 'VRT Gaming', 'Aizer', 'Rohan', 'Josh', 'Dolphe', 'Tbnr', 'Bio', 'Verx', 'Doggy', 'NF89', 'Triv', 'Rex', 'Duko', 'Arkiver', 'Caliper'];

            if (chance < 0.15) { // 15% chance for a negative event
                isFail = true;
                const thief = thieves[Math.floor(Math.random() * thieves.length)];
                const thief2 = thieves.filter(t => t !== thief)[Math.floor(Math.random() * (thieves.length - 1))];

                if (inventory.fish > 1) { // Thief eats fish
                    inventory.fish -= 2;
                    resultMessage = `${thief} was hungry and ate your fish!\n**-2**🐟`;
                } else if (inventory.rareFish > 0) { // Thief eats rare fish
                    inventory.rareFish -= 1;
                    resultMessage = `${thief} was hungry and ate your rare fish!\n**-1**🐠`;
                } else if (inventory.wood > 0 || inventory.palmLeaves > 0 || inventory.stone > 0 || inventory.copper > 0) { 
                    // Scuffle with thieves, lose multiple resources
                    inventory.wood -= Math.min(1, inventory.wood);
                    inventory.palmLeaves -= Math.min(1, inventory.palmLeaves);
                    inventory.stone -= Math.min(1, inventory.stone);
                    inventory.copper -= Math.min(1, inventory.copper);
                    resultMessage = `You, ${thief}, and ${thief2} got into a scuffle at the fishing dock!\n**-1**🪵\n**-1**🌿\n**-1**🪨\n**-1**🔶`;
                } else { // Default to no resources and taunt
                    resultMessage = `${thief} saw you at the fishing dock and laughed at how poor you were!`;
                }
            } else { // Otherwise, catch 1-5 fish
                const fishAmount = Math.floor(Math.random() * 5) + 1; // 1 to 5 fish
                inventory.fish += fishAmount;
                resultMessage = `You caught some fish!\n**+${fishAmount}**🐟`;

                // Check for bonuses
                const bonusChances = [
                    { chance: 0.33, action: () => {
                        const rareFishAmount = Math.floor(Math.random() * 3) + 1; // 1 to 3 rare fish
                        inventory.rareFish += rareFishAmount;
                        return { name: 'Bonus!', value: `You caught some rare fish!\n**+${rareFishAmount}**🐠` };
                    }},
                    { chance: 0.10, action: () => {
                        const superRareFishAmount = Math.floor(Math.random() * 2) + 1; // 1 to 2 super rare fish
                        inventory.superRareFish += superRareFishAmount;
                        return { name: '〈Rare Bonus!〉', value: `You caught a super rare fish!\n**+${superRareFishAmount}**🐡` };
                    }},
                    { chance: 0.04, action: () => {
                        inventory.legendaryFish += 1;
                        return { name: '【🦈ULTRA RARE BONUS!🦈】', value: '**+1**🦈' };
                    }},
                    { chance: 0.15, action: () => {
                        // Define the possible items and their quantity ranges for the crate
                        const items = [
                            { type: 'gold', emoji: '✨', min: 1, max: 3 },
                            { type: 'rope', emoji: '🪢', min: 1, max: 3 },
                            { type: 'wood', emoji: '🪵', min: 1, max: 7 },
                            { type: 'stone', emoji: '🪨', min: 1, max: 7 },
                            { type: 'palmLeaves', emoji: '🌿', min: 1, max: 7 },
                            { type: 'copper', emoji: '🔶', min: 1, max: 7 }
                        ];

                        // Shuffle items and pick the first 3
                        const shuffledItems = items.sort(() => 0.5 - Math.random()).slice(0, 3);

                        // Initialize crateItems object
                        const crateItems = {};

                        // Generate random quantities for the selected items
                        shuffledItems.forEach(item => {
                            crateItems[item.type] = Math.floor(Math.random() * (item.max - item.min + 1)) + item.min;
                        });

                        // Update inventory with crate items
                        inventory.gold += crateItems.gold || 0;
                        inventory.rope += crateItems.rope || 0;
                        inventory.wood += crateItems.wood || 0;
                        inventory.stone += crateItems.stone || 0;
                        inventory.palmLeaves += crateItems.palmLeaves || 0;
                        inventory.copper += crateItems.copper || 0;

                        // Construct the crate result message
                        return { name: 'Bonus!', value: `You found a crate!📦\n${shuffledItems.map(item => `**+${crateItems[item.type]}** ${item.emoji}`).join('\n')}` };
                    }},
                    { chance: 0.04, action: () => {
                        if (!inventory.negadomBattery) {
                            inventory.negadomBattery = true;
                            return { name: '【🔋ULTRA RARE BONUS!🔋】', value: 'You found the Negadom Destroyer battery!\n**+1**🔋' };
                        }
                        return null; // If they already have it, do nothing
                    }},
                ];

                bonuses.push(...bonusChances.map(bonus => Math.random() < bonus.chance ? bonus.action() : null).filter(Boolean));
            }

            // Save inventory updates
            await inventory.save();

            // Construct the embed
            const embed = new EmbedBuilder()
                .setDescription(resultMessage)
                .setThumbnail(interaction.user.displayAvatarURL({ dynamic: true }))
                .setFooter({ text: `Total fish: ${inventory.fish}` });
                
            // Add bonus fields
            if (bonuses.length > 0) {
                bonuses.forEach(bonus => {
                    if (bonus) {
                        embed.addFields(bonus);
                    }
                });
            }

            // Set embed title and color
            if (isFail) {
                embed.setTitle('Failure! [🎣]')
                embed.setColor('#ff0000');
            } else {
                embed.setTitle('Success! [🎣]')
                embed.setColor('#00ff00');
            }

            // Send the embed
            await interaction.reply({ embeds: [embed] });

        } catch (error) {
            console.error('Error during fishing:', error);
            await interaction.reply({ content: 'An error occurred while fishing. Please try again later.', ephemeral: true });
        }
    }
};
