const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('mine')
        .setDescription('Mine stone to collect resources.'),
    async execute(interaction) {
        const userId = interaction.user.id;
        const user = await User.findOrCreate({ where: { discordId: userId } });

        const currentTime = Date.now();
        const lastMineTime = user[0].lastMine || 0;
        const cooldown = 50 * 1000; // 50 seconds

        if (currentTime - lastMineTime < cooldown) {
            const timeLeft = ((cooldown - (currentTime - lastMineTime)) / 1000).toFixed(1);
            return interaction.reply({
                content: `You need to wait ${timeLeft} more seconds before mining again.`,
                ephemeral: true,
            });
        }

        const stoneAmount = Math.floor(Math.random() * 3) + 1; // Random stone between 1-3

        user[0].stone = (user[0].stone || 0) + stoneAmount;
        user[0].lastMine = currentTime;
        await user[0].save();

        const embed = new EmbedBuilder()
            .setColor(0x7289DA) // A nice blue color
            .setTitle('Mine Command')
            .setDescription(`You obtained **${stoneAmount}** 🪨`)
            .setFooter({ text: `Total stone: ${user[0].stone} 🪨` });

        return interaction.reply({ embeds: [embed] });
    },
};
