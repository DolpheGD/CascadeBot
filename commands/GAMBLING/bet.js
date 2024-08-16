const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('bet')
        .setDescription('Bet your wood or stone on a coin flip!')
        .addIntegerOption(option =>
            option.setName('amount')
                .setDescription('The amount of wood or stone to bet')
                .setRequired(true))
        .addStringOption(option =>
            option.setName('resource')
                .setDescription('Choose the resource to bet')
                .setRequired(true)
                .addChoices(
                    { name: 'Wood', value: 'wood' },
                    { name: 'Stone', value: 'stone' }
                )),
    async execute(interaction) {
        const userId = interaction.user.id;
        const betAmount = interaction.options.getInteger('amount');
        const resource = interaction.options.getString('resource');
        const [user] = await User.findOrCreate({ where: { discordId: userId } });

        // Check if the user has enough of the selected resource
        if (user[resource] < betAmount) {
            return interaction.reply({ content: `You don't have enough ${resource}!`, ephemeral: true });
        }

        // Deduct the bet amount from the user's resource
        user[resource] -= betAmount;
        await user.save();

        // Create the initial embed message
        const embed = new EmbedBuilder()
            .setColor('#0099ff')
            .setTitle('Coin Flip!')
            .setDescription(`You bet **${betAmount}** ${resource === 'wood' ? '🌲' : '🪨'} on the coin flip! React with ⚪ for heads or ⚫ for tails.`);

        const message = await interaction.reply({ embeds: [embed], fetchReply: true });
        await message.react('⚪');
        await message.react('⚫');

        // Set up the reaction collector
        const filter = (reaction, user) => {
            return (reaction.emoji.name === '⚪' || reaction.emoji.name === '⚫') && user.id === interaction.user.id;
        };

        const collector = message.createReactionCollector({ filter, time: 15000 });

        collector.on('collect', async (reaction) => {
            collector.stop(); // Stop the collector on first reaction

            const flipResult = Math.random() < 0.5 ? '⚪' : '⚫';
            let resultMessage;

            if (reaction.emoji.name === flipResult) {
                user[resource] += betAmount * 2;
                resultMessage = `Congratulations! The coin landed on ${flipResult}. You've won **${betAmount * 2}** ${resource === 'wood' ? '🌲' : '🪨'}!`;
            } else {
                resultMessage = `Sorry! The coin landed on ${flipResult}. You lost **${betAmount}** ${resource === 'wood' ? '🌲' : '🪨'}.`;
            }

            await user.save();

            const resultEmbed = new EmbedBuilder()
                .setColor(flipResult === reaction.emoji.name ? '#00ff00' : '#ff0000')
                .setTitle('Coin Flip Result')
                .setDescription(resultMessage);

            await interaction.editReply({ embeds: [resultEmbed] });
        });

        collector.on('end', async (collected, reason) => {
            if (reason === 'time') {
                user[resource] += betAmount; // Refund the bet if the collector times out
                await user.save();
                await interaction.editReply({ content: 'You took too long to respond! Your bet has been refunded.', embeds: [] });
            }
        });
    },
};
