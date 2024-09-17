const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('leaderboard')
        .setDescription('Display the top users by power')
        .addIntegerOption(option =>
            option.setName('count')
                .setDescription('Number of users to display (top 10, 25, or 100)')
                .setRequired(false)
                .addChoices(
                    { name: 'Top 10', value: 10 },
                    { name: 'Top 25', value: 25 },
                    { name: 'Top 100', value: 100 }
                )
        ),

    async execute(interaction) {
        try {
            await interaction.deferReply();
            
            // Fetch the count from the command option (default to 25 if not provided)
            const count = interaction.options.getInteger('count') || 25;

            // Fetch all users with their associated inventory
            const users = await User.findAll({
                include: {
                    model: Inventory,
                    as: 'inventory'
                }
            });

            // Calculate power and prepare leaderboard data
            const leaderboard = users.map(user => {
                const inventory = user.inventory || {};
                const power =   inventory.wood + inventory.stone + inventory.palmLeaves + inventory.copper + inventory.berries + inventory.fish +
                                2 * inventory.apples + 3 * inventory.rope + 3 * inventory.watermelon + 3 * inventory.rareFish +
                                5 * inventory.superRareFish + 5 * inventory.gold + 5 * inventory.cloth +
                                15 * inventory.legendaryFish + 25 * inventory.banana + 
                                15 * inventory.metalParts + 
                                50 * inventory.ruby + 150 * inventory.coconut + 
                                250 * inventory.diamond + 
                                400 * inventory.negadomBattery
                return {
                    username: user.username,
                    power: power,
                    discordId: user.discordId // Store Discord ID for fetching avatar
                };
            });

            // Sort by power in descending order and slice based on the count provided
            leaderboard.sort((a, b) => b.power - a.power);
            const tops = leaderboard.slice(0, count);

            // Create leaderboard description
            const description = tops.map((entry, index) => `${index + 1}. ${entry.username}: ${entry.power}⚡`).join('\n');

            // Fetch the user with the highest power for the thumbnail
            const topUser = tops[0];
            const topUserAvatar = topUser ? await interaction.client.users.fetch(topUser.discordId).then(user => user.displayAvatarURL()) : null;

            // Create the embed
            const embed = new EmbedBuilder()
                .setColor('#0099ff')
                .setTitle(`Leaderboard (Top ${count} by Power)`)
                .setDescription(description)
                .setFooter({ text: 'Power is calculated using a weighted sum of items' });

            if (topUserAvatar) {
                embed.setThumbnail(topUserAvatar);
            }

            return interaction.editReply({ embeds: [embed] });
        } catch (error) {
            console.error('Error fetching leaderboard:', error);
            return interaction.editReply({ content: 'An error occurred while fetching the leaderboard. Please try again later.', ephemeral: true });
        }
    },
};
