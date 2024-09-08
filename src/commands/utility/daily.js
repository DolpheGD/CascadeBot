const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('daily')
        .setDescription('Claim your daily reward!'),

    async execute(interaction) {
        const userId = interaction.user.id;

        await interaction.deferReply();

        // Retrieve the user and inventory, or create them if they don't exist
        const [user] = await User.findOrCreate({ where: { discordId: userId } });
        const [inventory] = await Inventory.findOrCreate({ where: { userId: user.id } });

        const now = new Date();

        // Convert current time to UTC-7 (Pacific Time)
        const utc7Offset = -7 * 60;
        const utc7Time = new Date(now.getTime() + (utc7Offset * 60 * 1000));

        // Determine the last reset time (12:00 AM UTC-7)
        const lastReset = new Date(utc7Time);
        lastReset.setUTCHours(7, 0, 0, 0); // Set time to 12:00 AM UTC-7

        if (utc7Time < lastReset) {
            lastReset.setDate(lastReset.getDate() - 1); // If it's before 12:00 AM, last reset was the previous day
        }

        // Check if the user has already claimed their daily reward
        if (user.lastDaily && user.lastDaily >= lastReset) {
            const resetTimeLeft = lastReset.getTime() + 24 * 60 * 60 * 1000 - utc7Time.getTime();
            const hoursLeft = Math.ceil(resetTimeLeft / (60 * 60 * 1000));
            return interaction.editReply({ content: `You have already claimed your daily reward! Please wait ${hoursLeft} more hour(s) before claiming again.`, ephemeral: true });
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
            .setFooter({ text: 'Come back after the next reset to claim again!' });

        await interaction.editReply({ embeds: [embed] });
    },
};
