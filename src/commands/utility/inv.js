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

            // Build the inventory display string conditionally
            let inventoryDisplay = '';

            if (inventory.wood > 0) inventoryDisplay += `**Wood**: ${inventory.wood}🪵\n`;
            if (inventory.stone > 0) inventoryDisplay += `**Stone**: ${inventory.stone}🪨\n`;
            if (inventory.palmLeaves > 0) inventoryDisplay += `**Palm Leaves**: ${inventory.palmLeaves}🌿\n`;
            if (inventory.rope > 0) inventoryDisplay += `**Rope**: ${inventory.rope}🪢\n`;
            if (inventory.copper > 0) inventoryDisplay += `**Copper**: ${inventory.copper}🔶\n`;
            if (inventory.gold > 0) inventoryDisplay += `**Gold**: ${inventory.gold}✨\n`;
            if (inventory.ruby > 0) inventoryDisplay += `**Ruby**: ${inventory.ruby}♦️\n`;
            if (inventory.diamond > 0) inventoryDisplay += `**Diamond**: ${inventory.diamond}💎\n`;
            if (inventory.fish > 0) inventoryDisplay += `**Fish**: ${inventory.fish}🐟\n`;
            if (inventory.rareFish > 0) inventoryDisplay += `**Rare Fish**: ${inventory.rareFish}🐠\n`;
            if (inventory.superRareFish > 0) inventoryDisplay += `**Super Rare Fish**: ${inventory.superRareFish}🐡\n`;
            if (inventory.legendaryFish > 0) inventoryDisplay += `**Legendary Fish**: ${inventory.legendaryFish}🦈\n`;
            if (inventory.negadomBattery) inventoryDisplay += `**Negadom Destroyer Battery**: 1🔋\n`;

            if (!inventoryDisplay) {
                return interaction.reply({ content: `${targetUser.username}'s inventory is empty.`, ephemeral: true });
            }

            // Create an embed to display the inventory
            const embed = new EmbedBuilder()
                .setColor('#0099ff')
                .setTitle(`${targetUser.username}'s Inventory`)
                .setThumbnail(targetUser.displayAvatarURL()) // Add the user's avatar as a thumbnail
                .setDescription(inventoryDisplay)
                .setFooter({ 
                    text: `Total Power: ${
                        inventory.gold + 
                        10 * inventory.ruby + 
                        100 * inventory.diamond +
                        inventory.fish +
                        2 * inventory.rareFish +
                        5 * inventory.superRareFish + 
                        15 * inventory.legendaryFish +
                        1000 * inventory.negadomBattery
                    } ⚡`
                });

            return interaction.reply({ embeds: [embed] });
        } catch (error) {
            console.error('Error fetching inventory:', error);
            return interaction.reply({ content: 'An error occurred while fetching the inventory. Please try again later.', ephemeral: true });
        }
    },
};
