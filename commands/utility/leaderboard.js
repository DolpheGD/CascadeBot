const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('leaderboard')
        .setDescription('View the top 10 users with the most wood'),
    async execute(interaction) {
        try {
            // Fetch the top 10 users with the most wood
            const topUsers = await User.findAll({
                order: [['wood', 'DESC']], // Order by wood in descending order
                limit: 10 // Limit to the top 10 users
            });

            // Create an embed message
            const embed = new EmbedBuilder()
                .setColor('#0099ff') // Set the color of the embed
                .setTitle('Leaderboard:') // Set the title

            // Fetch usernames for each user and add to embed
            const promises = topUsers.map(async (user, index) => {
                const member = await interaction.guild.members.fetch(user.discordId); // Fetch member from the guild
                return { rank: index + 1, username: member.user.username, wood: user.wood };
            });

            const leaderboardData = await Promise.all(promises);

            leaderboardData.forEach(({ rank, username, wood }) => {
                embed.addFields(
                    { name: `${rank}. ${username}`, value: `${wood} 🌲`, inline: false }
                );
            });

            // Reply with the embed
            return interaction.reply({ embeds: [embed] });
        } catch (error) {
            console.error('Error fetching leaderboard:', error);
            return interaction.reply({ content: 'There was an error fetching the leaderboard.', ephemeral: true });
        }
    },
};