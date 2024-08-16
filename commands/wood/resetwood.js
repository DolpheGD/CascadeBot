const { SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const User = require('../../models/User');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('resetwood')
        .setDescription('Reset all users\' wood to 0.')
        .setDefaultMemberPermissions(PermissionFlagsBits.Administrator),

    async execute(interaction) {
        await User.update({ wood: 0 }, { where: {} });
        return interaction.reply({ content: 'All users\' wood has been reset to 0.', ephemeral: true});
    },
};