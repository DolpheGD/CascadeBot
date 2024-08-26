const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');
const { Op } = require('sequelize');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('daily')
        .setDescription('Claim your daily reward!'),

    async execute(interaction) {
        const userId = interaction.user.id;

        // Retrieve the user and inventory, or create them if they don't exist
        const [user] = await User.findOrCreate({ where: { discordId: userId } });
        const [inventory] = await Inventory.findOrCreate({ where: { userId: user.id } });

        const now = new Date();

        // Check if 24 hours have passed since the last daily claim
        if (user.lastDaily && now - user.lastDaily < 24 * 60 * 60 * 1000) {
            const hoursLeft = Math.ceil((24 * 60 * 60 * 1000 - (now - user.lastDaily)) / (60 * 60 * 1000));
            return interaction.reply({ content: `You have already claimed your daily reward! Please wait ${hoursLeft} more hour(s) before claiming again.`, ephemeral: true });
        }

        // Award resources
        const reward = {
            wood: 30,
            stone: 30,
            copper: 30,
            palmLeaves: 30,
            gold: 5,
        };

        inventory.wood += reward.wood;
        inventory.stone += reward.stone;
        inventory.copper += reward.copper;
        inventory.palmLeaves += reward.palmLeaves;
        inventory.gold += reward.gold;

        await inventory.save();

        // Update the lastDaily timestamp
        user.lastDaily = now;   
        await user.save();

        // Create an embed to show the awarded resources
        const embed = new EmbedBuilder()
            .setColor('#FFD700')
            .setTitle('Daily Reward')
            .setDescription('You have claimed your daily reward!')
            .setThumbnail(interaction.user.displayAvatarURL())
            .addFields(
                { name: 'Wood 🪵', value: `+${reward.wood}`, inline: true },
                { name: 'Stone 🪨', value: `+${reward.stone}`, inline: true },
                { name: 'Copper 🔶', value: `+${reward.copper}`, inline: true },
                { name: 'Palm Leaves 🌿', value: `+${reward.palmLeaves}`, inline: true },
                { name: 'Gold ✨', value: `+${reward.gold}`, inline: true }
            )
            .setFooter({ text: 'Come back in 24 hours to claim again!' });

        await interaction.reply({ embeds: [embed] });
    },
};
