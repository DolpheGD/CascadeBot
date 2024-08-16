const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('inv')
        .setDescription('View inventory'),
    async execute(interaction) {
        const userId = interaction.user.id;
        const [user] = await User.findOrCreate({ where: { discordId: userId } });

        // Create an embed message with user's avatar
        const embed = new EmbedBuilder()
            .setColor('#0099ff') // Set the color of the embed
            .setTitle('Your Inventory') // Set the title
            .setThumbnail(interaction.user.displayAvatarURL({ format: 'png', size: 128 })) // Set the user's avatar as the thumbnail
            .addFields(
                { name: 'Wood', value: `${user.wood} 🌲`, inline: false }, // Wood with emoji
                { name: 'Stone', value: `${user.stone || 0} 🪨`, inline: false } // Stone with emoji
            );

        return interaction.reply({ embeds: [embed] });
    },
};
