const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('bet')
        .setDescription('Bet your wood on heads or tails')
        .addIntegerOption(option =>
            option.setName('amount')
                .setDescription('Amount of wood to bet')
                .setRequired(true)),
                
    async execute(interaction) {
        const amount = interaction.options.getInteger('amount');
        const userId = interaction.user.id;

        console.log(`User ${interaction.user.username} is trying to bet ${amount} wood`);

        // Fetch the user from the database
        const [user] = await User.findOrCreate({ where: { discordId: userId } });

        // Check if the user has enough wood
        if (user.wood < amount) {
            return interaction.reply({ content: 'You do not have enough wood to place this bet!', ephemeral: true });
        }

        // Deduct the bet amount from the user's wood
        user.wood -= amount;
        await user.save();

        // Create an embed message for betting
        const betEmbed = new EmbedBuilder()
            .setColor('#0099ff')
            .setTitle('Bet on Heads or Tails')
            .setDescription(`You have bet ${amount} 🌲. React with ⚪ for heads or ⚫ for tails.`);

        const betMessage = await interaction.reply({ embeds: [betEmbed], fetchReply: true });

        console.log(`Bet message sent with ID: ${betMessage.id}`);

        // Add reaction emojis for heads and tails
        try {
            await betMessage.react('⚪'); // Heads
            await betMessage.react('⚫'); // Tails
            console.log('Reactions added to the bet message.');
        } catch (error) {
            console.error('Error adding reactions:', error);
        }

        // Set up a reaction collector
        const filter = (reaction, user) => {
            console.log(`Received reaction ${reaction.emoji.name} from ${user.username}`);
            return ['⚪', '⚫'].includes(reaction.emoji.name) && user.id === interaction.user.id;
        };

        const collector = betMessage.createReactionCollector({ filter, time: 25000 });

        collector.on('collect', async reaction => {
            console.log(`Collected ${reaction.emoji.name} from ${interaction.user.username}`);
            collector.stop(); // Stop collecting after the first reaction

            // Determine the outcome
            const result = Math.random() < 0.5 ? '⚪' : '⚫'; // Randomly choose heads or tails
            const win = reaction.emoji.name === result;

            let resultEmbed = new EmbedBuilder()
                .setColor(win ? '#00ff00' : '#ff0000')
                .setTitle(win ? 'Congratulations!' : 'You Lost!')
                .setDescription(win
                    ? `You won! Your wood has been doubled from ${amount} 🌲 to ${amount * 2} 🌲.`
                    : `You lost! Your remaining wood is ${user.wood} 🌲.`);

            if (win) {
                user.wood += amount * 2; // Double the bet
                await user.save();
            }

            await interaction.followUp({ embeds: [resultEmbed] });
        });

        collector.on('end', async (collected, reason) => {
            if (reason === 'time') {
                console.log('Reaction collector timed out');
                
                // Return the bet amount if the bet times out
                user.wood += amount;
                await user.save();

                const timeoutEmbed = new EmbedBuilder()
                    .setColor('#ff0000')
                    .setTitle('Bet Timed Out')
                    .setDescription('You did not react in time. Your bet has been canceled and your wood has been returned.');

                await interaction.followUp({ embeds: [timeoutEmbed] });
            }
        });
    },
};
