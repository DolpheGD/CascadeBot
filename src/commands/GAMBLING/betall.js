const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');

// Create a Set to track users currently using the betall command
const activeBets = new Set();

module.exports = {
    data: new SlashCommandBuilder()
        .setName('betall')
        .setDescription('Bet your entire inventory by flipping a coin.'),

    async execute(interaction) {
        const userId = interaction.user.id;

        // Check if the user is already in an active bet
        if (activeBets.has(userId)) {
            return interaction.reply({ content: 'You already have an ongoing bet. Please wait until it finishes.', ephemeral: true });
        }

        // Add the user to the active bets set
        activeBets.add(userId);

        // Valid resources
        const validResources = ['wood', 'stone', 'palmLeaves', 'gold', 'rope', 'diamond', 'ruby', 'copper'];

        // Check if user has enough of any resource to bet
        const [user] = await User.findOrCreate({ where: { discordId: userId } });
        const [inventory] = await Inventory.findOrCreate({ where: { userId: user.id } });

        const totalBet = validResources.reduce((sum, resource) => sum + inventory[resource], 0);

        if (totalBet === 0) {
            // Remove the user from the active bets set
            activeBets.delete(userId);
            return interaction.reply({ content: `You do not have any resources to bet.`, ephemeral: true });
        }

        // Create the embed for betting
        const embed = new EmbedBuilder()
            .setColor('#0099ff')
            .setThumbnail(interaction.user.displayAvatarURL()) // Add the user's avatar as a thumbnail
            .setTitle('Coin Flip!')
            .setDescription(`You are betting your entire inventory. React with ⚪ for heads or ⚫ for tails.`);

        // Send the embed and add reactions
        const message = await interaction.reply({ embeds: [embed], fetchReply: true });
        await message.react('⚪');
        await message.react('⚫');

        // Set up a reaction collector
        const filter = (reaction, user) => {
            return ['⚪', '⚫'].includes(reaction.emoji.name) && user.id === interaction.user.id;
        };

        const collector = message.createReactionCollector({ filter, time: 20000 }); // 20 seconds

        collector.on('collect', async (reaction) => {
            // Determine the result of the coin flip
            const result = Math.random() < 0.5 ? '⚪' : '⚫';
            const isWin = reaction.emoji.name === result;

            // Add win/lose message
            embed.setDescription(isWin ? getRandomWinMessage() : getRandomLoseMessage());

            // Update the inventory based on the result and display each resource sequentially
            validResources.forEach(resource => {
                const amount = inventory[resource];
                if (amount > 0) {
                    if (isWin) {
                        inventory[resource] += amount;
                        embed.addFields({ name: '\u200B', value: `+**${amount}** ${getEmojiForResource(resource)}`, inline: true });
                    } else {
                        inventory[resource] = 0;
                        embed.addFields({ name: '\u200B', value: `-**${amount}** ${getEmojiForResource(resource)}`, inline: true });
                    }
                }
            });

            embed.setColor(isWin ? '#00ff00' : '#ff0000');
            await inventory.save();
            await message.edit({ embeds: [embed] });

            collector.stop();
        });

        collector.on('end', (collected, reason) => {
            // Remove the user from the active bets set
            activeBets.delete(userId);

            if (reason === 'time') {
                embed.setDescription('Time is up! You did not react in time.');
                embed.setFooter({ text: 'No changes to your inventory.' });
                message.edit({ embeds: [embed] });
            }
        });
    },
};

// Helper function to get the emoji for the resource
function getEmojiForResource(resource) {
    switch (resource) {
        case 'wood': return '🪵';
        case 'stone': return '🪨';
        case 'palmLeaves': return '🌿';
        case 'gold': return '✨';
        case 'rope': return '🪢';
        case 'diamond': return '💎';
        case 'ruby': return '♦️';
        case 'copper': return '🔶';
        default: return '';
    }
}

// Helper function to get a random win message
function getRandomWinMessage() {
    const winMessages = ['OHAMAGAD!!!!', 'GGGGGGGGGG!!!!', 'THE GOAT! THE GOAT!!!', 'YOU DID IT!! YOU WON THE 50/50!!!!!!'];
    return winMessages[Math.floor(Math.random() * winMessages.length)];
}

// Helper function to get a random lose message
function getRandomLoseMessage() {
    const loseMessages = ['Can we get an f in the chat for this guy...', 'BLUD LOST IT ALL!!!!', 'Its okay to cry.... Not everyone is lucky in life....', 'Welp that sucks. However, did you know that 99% of gamblers quit before they win big?'];
    return loseMessages[Math.floor(Math.random() * loseMessages.length)];
}
