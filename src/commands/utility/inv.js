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
            await interaction.deferReply();
            
            // Find the user
            const user = await User.findOne({ where: { discordId: userId } });
            if (!user) {
                return interaction.editReply({ content: `${targetUser.username} does not have an inventory yet. They need to use commands like /chop or /mine to gather resources.`, ephemeral: true });
            }

            // Find the user's inventory
            const inventory = await Inventory.findOne({ where: { userId: user.id } });
            if (!inventory) {
                return interaction.editReply({ content: `${targetUser.username}'s inventory is empty. They need to use commands like /chop or /mine to gather resources.`, ephemeral: true });
            }

            // Build the inventory display string conditionally
            let inventoryDisplay = '';

            inventoryDisplay += `### --General Resources--\n`;
            if (inventory.wood > 0) inventoryDisplay += `**Wood**: ${inventory.wood}🪵\n`;
            if (inventory.stone > 0) inventoryDisplay += `**Stone**: ${inventory.stone}🪨\n`;
            if (inventory.palmLeaves > 0) inventoryDisplay += `**Palm Leaves**: ${inventory.palmLeaves}🌿\n`;
            if (inventory.rope > 0) inventoryDisplay += `**Rope**: ${inventory.rope}🪢\n`;
            if (inventory.cloth > 0) inventoryDisplay += `**Cloth**: ${inventory.cloth}🧶\n`;

            inventoryDisplay += `\n### --Fruit--\n`;
            if (inventory.berries > 0) inventoryDisplay += `**Berries**: ${inventory.berries}🫐\n`;
            if (inventory.apples > 0) inventoryDisplay += `**Apples**: ${inventory.apples}🍎\n`;
            if (inventory.watermelon > 0) inventoryDisplay += `**Watermelon**: ${inventory.watermelon}🍉\n`;
            if (inventory.banana > 0) inventoryDisplay += `**Banana**: ${inventory.banana}🍌\n`;
            if (inventory.coconut > 0) inventoryDisplay += `**Coconut**: ${inventory.coconut}🥥\n`;

            inventoryDisplay += `\n### --Ores--\n`;
            if (inventory.copper > 0) inventoryDisplay += `**Copper**: ${inventory.copper}🔶\n`;
            if (inventory.gold > 0) inventoryDisplay += `**Gold**: ${inventory.gold}✨\n`;
            if (inventory.ruby > 0) inventoryDisplay += `**Ruby**: ${inventory.ruby}♦️\n`;
            if (inventory.diamond > 0) inventoryDisplay += `**Diamond**: ${inventory.diamond}💎\n`;
            
            inventoryDisplay += `\n### --Fish--\n`;
            if (inventory.fish > 0) inventoryDisplay += `**Fish**: ${inventory.fish}🐟\n`;
            if (inventory.rareFish > 0) inventoryDisplay += `**Rare Fish**: ${inventory.rareFish}🐠\n`;
            if (inventory.superRareFish > 0) inventoryDisplay += `**Super Rare Fish**: ${inventory.superRareFish}🐡\n`;
            if (inventory.legendaryFish > 0) inventoryDisplay += `**Legendary Fish**: ${inventory.legendaryFish}🦈\n`;
            
            inventoryDisplay += `\n### --Tech--\n`;
            if (inventory.metalParts > 0) inventoryDisplay += `**Metal Parts**: ${inventory.metalParts}⚙️\n`;
            if (inventory.negadomBattery) inventoryDisplay += `**Negadom Destroyer Battery**: 1🔋\n`;

            if (!inventoryDisplay) {
                return interaction.editReply({ content: `${targetUser.username}'s inventory is empty.`, ephemeral: true });
            }

            // Create an embed to display the inventory
            const embed = new EmbedBuilder()
                .setColor('#0099ff')
                .setTitle(`${targetUser.username}'s Inventory`)
                .setThumbnail(targetUser.displayAvatarURL()) // Add the user's avatar as a thumbnail
                .setDescription(inventoryDisplay)
                .setFooter({ 
                    text: `Total Power: ${
                        inventory.wood + inventory.stone + inventory.palmLeaves + inventory.copper + inventory.berries + inventory.fish +
                        2 * inventory.apples + 3 * inventory.rope + 3 * inventory.watermelon + 3 * inventory.rareFish +
                        5 * inventory.superRareFish + 5 * inventory.gold + 5 * inventory.cloth +
                        15 * inventory.legendaryFish + 20 * inventory.banana + 
                        15 * inventory.metalParts + 
                        50 * inventory.ruby + 150 * inventory.coconut + 
                        250 * inventory.diamond + 
                        400 * inventory.negadomBattery
                    } ⚡`
                });

            return interaction.editReply({ embeds: [embed] });
        } catch (error) {
            console.error('Error fetching inventory:', error);
            return interaction.editReply({ content: 'An error occurred while fetching the inventory. Please try again later.', ephemeral: true });
        }
    },
};
