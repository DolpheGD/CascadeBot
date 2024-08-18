const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('inv')
        .setDescription('Check your inventory'),

    async execute(interaction) {
        const userId = interaction.user.id;

        try {
            // Find the user
            const user = await User.findOne({ where: { discordId: userId } });
            if (!user) {
                return interaction.reply({ content: 'You do not have an inventory yet. Use commands like /chop or /mine to gather resources.', ephemeral: true });
            }

            // Find the user's inventory using the correct foreign key
            const inventory = await Inventory.findOne({ where: { userId: user.id } }); // Use user.id here
            if (!inventory) {
                return interaction.reply({ content: 'Your inventory is empty. Use commands like /chop or /mine to gather resources.', ephemeral: true });
            }

            // Create an embed to display the inventory
            const embed = new EmbedBuilder()
                .setColor('#0099ff')
                .setTitle(`${interaction.user.username}'s Inventory`)
                .setThumbnail(interaction.user.displayAvatarURL()) // Add the user's avatar as a thumbnail
                .addFields(
                    { name: 'Wood', value: `🪵 ${inventory.wood}`, inline: true },
                    { name: 'Stone', value: `🪨 ${inventory.stone}`, inline: true },
                    { name: 'Palm Leaves', value: `🌿 ${inventory.palmLeaves}`, inline: true },
                    { name: 'Gold', value: `🏅 ${inventory.gold}`, inline: true },
                    { name: 'Rope', value: `🪢 ${inventory.rope}`, inline: true }
                )
                .setFooter({ text: `Total Power: ${inventory.wood + 2 * inventory.stone + 2 * inventory.palmLeaves + 4 * inventory.rope + 4 * inventory.gold} ⚡` });

            return interaction.reply({ embeds: [embed] });
        } catch (error) {
            console.error('Error fetching inventory:', error);
            return interaction.reply({ content: 'An error occurred while fetching your inventory. Please try again later.', ephemeral: true });
        }
    },
};
