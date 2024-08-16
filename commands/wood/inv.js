const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('inv')
        .setDescription('View inventory'),
    async execute(interaction) {
        const userId = interaction.user.id;
        const [user] = await User.findOrCreate({ where: { discordId: userId } });

        // Create an embed message
        const embed = new EmbedBuilder()
            .setColor('#0099ff') // Set the color of the embed
            .setTitle('Your Inventory') // Set the title
            .addFields(
                { name: 'Wood', value: `${user.wood} 🌲`, inline: false } // Add a field with emoji
            )

        return interaction.reply({ embeds: [embed] });
    },
};