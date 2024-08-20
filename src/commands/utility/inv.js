const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('inv')
        .setDescription('Check your inventory or someone else\'s inventory')
        .addUserOption(option => 
            option.setName('target')
                .setDescription('The user whose inventory you want to check')
                .setRequired(false)),

    async execute(interaction) {
        // Get the target user if provided, otherwise use the command issuer
        const targetUser = interaction.options.getUser('target') || interaction.user;
        const userId = targetUser.id;

        try {
            // Find the user
            const user = await User.findOne({ where: { discordId: userId } });
            if (!user) {
                return interaction.reply({ content: `${targetUser.username} does not have an inventory yet. They need to use commands like /chop or /mine to gather resources.`, ephemeral: true });
            }

            // Find the user's inventory
            const inventory = await Inventory.findOne({ where: { userId: user.id } });
            if (!inventory) {
                return interaction.reply({ content: `${targetUser.username}'s inventory is empty. They need to use commands like /chop or /mine to gather resources.`, ephemeral: true });
            }

            // Create an embed to display the inventory
            const embed = new EmbedBuilder()
                .setColor('#0099ff')
                .setTitle(`${targetUser.username}'s Inventory`)
                .setThumbnail(targetUser.displayAvatarURL()) // Add the user's avatar as a thumbnail
                .addFields(
                    { name: 'Wood', value: `🪵 ${inventory.wood}`, inline: true },
                    { name: 'Stone', value: `🪨 ${inventory.stone}`, inline: true },
                    { name: 'Palm Leaves', value: `🌿 ${inventory.palmLeaves}`, inline: true },
                    { name: 'Rope', value: `🪢 ${inventory.rope}`, inline: true },
                    { name: 'Copper', value: `🔶 ${inventory.copper}`, inline: true },
                    { name: 'Gold', value: `✨ ${inventory.gold}`, inline: true },
                    { name: 'Ruby', value: `♦️ ${inventory.ruby}`, inline: true },
                    { name: 'Diamond', value: `💎 ${inventory.diamond}`, inline: true }
                )
                .setFooter({ text: `Total Power: ${inventory.wood + inventory.palmLeaves + 3 * inventory.rope + 
                                            inventory.stone + 2 * inventory.copper + 5 * inventory.gold + 50 * inventory.ruby + 250 * inventory.diamond} ⚡` });

            return interaction.reply({ embeds: [embed] });
        } catch (error) {
            console.error('Error fetching inventory:', error);
            return interaction.reply({ content: 'An error occurred while fetching the inventory. Please try again later.', ephemeral: true });
        }
    },
};
