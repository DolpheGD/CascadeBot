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

            if (!tools || !tools.fishingRod) {
                return interaction.reply({ content: 'You do not own a fishing rod.', ephemeral: true });
            }

            // Check cooldown
            const now = Date.now();
            const cooldown = 20 * 1000; // 2s0 seconds
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

            // Determine fishing result
            const chance = Math.random();
            let resultMessage = '';
            let isFail = false; // Default to green

            // Fetch or create the user's inventory
            let inventory = await Inventory.findOne({ where: { userId: user.id } });
            if (!inventory) {
                inventory = await Inventory.create({ userId: user.id });
            }

            if (chance < 0.10) {
                isFail = true;
                resultMessage = 'You caught nothing!';
            } else if (chance < 0.50) {
                const fishAmount = Math.floor(Math.random() * 5) + 1; // 1 to 5 fish
                inventory.fish += fishAmount;
                await inventory.save();
                resultMessage = `You caught some fish!\n**+${fishAmount}** 🐟`;
            } else if (chance < 0.70) {
                const rareFishAmount = Math.floor(Math.random() * 3) + 1; // 1 to 3 rare fish
                inventory.rareFish += rareFishAmount;
                await inventory.save();
                resultMessage = `You caught a rare fish!\n**+${rareFishAmount}** 🐠`;
            } else if (chance < 0.80) {
                const superRareFishAmount = Math.floor(Math.random() * 2) + 1; // 1 to 2 super rare fish
                inventory.superRareFish += superRareFishAmount;
                await inventory.save();
                resultMessage = `You caught a super rare fish!\n**+${superRareFishAmount}** 🐡`;
            } else if (chance < 0.85) {
                inventory.legendaryFish += 1;
                await inventory.save();
                resultMessage = 'You caught a legendary fish!\n**+1** 🦈';
            } else if (chance < 0.99) { // crate stuff
                // Define the possible items and their quantity ranges
                const items = [
                    { type: 'gold', emoji: '✨', min: 1, max: 3 },
                    { type: 'rope', emoji: '🪢', min: 1, max: 3 },
                    { type: 'wood', emoji: '🪵', min: 1, max: 7 },
                    { type: 'stone', emoji: '🪨', min: 1, max: 7 },
                    { type: 'palmLeaves', emoji: '🌿', min: 1, max: 7 },
                    { type: 'copper', emoji: '🔶', min: 1, max: 7}
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
                await inventory.save();

                // Construct result message
                const itemDescriptions = shuffledItems.map(item => 
                    `**+${crateItems[item.type]}** ${item.emoji}`
                ).join('\n');

                resultMessage = `You found a crate!📦\n${itemDescriptions}`;

            } else if (chance < 1.0) {
                if (!inventory.negadomBattery) {
                    inventory.negadomBattery = true;
                    await inventory.save();
                    resultMessage = 'You found the Negadom Destroyer battery!\n**+1**🔋';
                } else {
                    resultMessage = 'You caught nothing!';
                    isFail = true;
                }
            }

            // Construct the embed
            const embed = new EmbedBuilder()
                .setDescription(resultMessage)
                .setThumbnail(interaction.user.displayAvatarURL({ dynamic: true }));

            if (!isFail){
                embed.setTitle('Success! [🎣]')
                embed.setColor('#00ff00')
            }
            else{
                embed.setTitle('Failure! [🎣]')
                embed.setColor('#ff0000')
            }

            // Reply with the result
            return interaction.reply({ embeds: [embed]});

        } catch (error) {
            console.error('Error during fishing:', error);
            return interaction.reply({ content: 'There was an error while fishing.', ephemeral: true });
        }
    },
};
