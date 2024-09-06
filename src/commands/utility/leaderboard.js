const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('leaderboard')
        .setDescription('Display the top 10 users by power'),

    async execute(interaction) {
        try {
            await interaction.deferReply();
            
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
                                5 * inventory.superRareFish + 5 * inventory.gold + 
                                15 * inventory.legendaryFish +
                                15 * inventory.metalParts +
                                50 * inventory.ruby + 
                                150 * inventory.diamond + 
                                250 * inventory.negadomBattery;
                return {
                    username: user.username,
                    power: power,
                    discordId: user.discordId // Store Discord ID for fetching avatar
                };
            });

            // Sort by power in descending order and get top 10
            leaderboard.sort((a, b) => b.power - a.power);
            const top10 = leaderboard.slice(0, 10);

            // Create leaderboard description
            const description = top10.map((entry, index) => `${index + 1}. ${entry.username}: ${entry.power}⚡`).join('\n');

            // Fetch the user with the highest power for the thumbnail
            const topUser = top10[0];
            const topUserAvatar = topUser ? await interaction.client.users.fetch(topUser.discordId).then(user => user.displayAvatarURL()) : null;

            // Create the embed
            const embed = new EmbedBuilder()
                .setColor('#0099ff')
                .setTitle('Leaderboard (Power)')
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
