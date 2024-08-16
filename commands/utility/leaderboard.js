const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('leaderboard')
        .setDescription('Display the top 10 users by wood or stone')
        .addStringOption(option =>
            option.setName('resource')
                .setDescription('Choose the resource to rank by')
                .setRequired(true)
                .addChoices(
                    { name: 'Wood', value: 'wood' },
                    { name: 'Stone', value: 'stone' }
                )),
    async execute(interaction) {
        const resource = interaction.options.getString('resource');

        // Find the top 10 users sorted by the selected resource
        const topUsers = await User.findAll({
            order: [[resource, 'DESC']],
            limit: 10,
        });

        const leaderboard = topUsers.map((user, index) => {
            return `${index + 1}. <@${user.discordId}> - ${user[resource]} ${resource === 'wood' ? '🌲' : '🪨'}`;
        }).join('\n');

        const embed = new EmbedBuilder()
            .setColor('#0099ff')
            .setTitle(`Top 10 Users by ${resource.charAt(0).toUpperCase() + resource.slice(1)}`)
            .setDescription(leaderboard || 'No data available.');

        await interaction.reply({ embeds: [embed] });
    },
};
