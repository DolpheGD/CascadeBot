const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');

// Object to track active bets
const activeBets = new Map();

module.exports = {
    data: new SlashCommandBuilder()
        .setName('bet')
        .setDescription('Bet an amount of a resource by flipping a coin.')
        .addStringOption(option =>
            option.setName('resource')
                .setDescription('The resource you want to bet (wood, stone, palmLeaves, gold, rope, diamond, ruby, copper)')
                .setRequired(true)
                .addChoices(
                    { name: 'Wood', value: 'wood' },
                    { name: 'Stone', value: 'stone' },
                    { name: 'Palm Leaves', value: 'palmLeaves' },
                    { name: 'Gold', value: 'gold' },
                    { name: 'Rope', value: 'rope' },
                    { name: 'Diamond', value: 'diamond' },
                    { name: 'Ruby', value: 'ruby' },
                    { name: 'Copper', value: 'copper' }
                ))
        .addIntegerOption(option =>
            option.setName('amount')
                .setDescription('The amount of the resource you want to bet')
                .setRequired(true)),

    async execute(interaction) {
        const resource = interaction.options.getString('resource');
        const amount = interaction.options.getInteger('amount');
        const userId = interaction.user.id;

        // Check if the user already has an active bet
        if (activeBets.has(userId)) {
            return interaction.reply({ content: 'You already have an active bet! Please wait until it is resolved.', ephemeral: true });
        }

        // Valid resources
        const validResources = ['wood', 'stone', 'palmLeaves', 'gold', 'rope', 'diamond', 'ruby', 'copper'];
        if (!validResources.includes(resource)) {
            return interaction.reply({ content: 'Invalid resource. Please choose from wood, stone, palmLeaves, gold, rope, diamond, ruby, or copper.', ephemeral: true });
        }

        // Validate the amount
        if (amount <= 0) {
            return interaction.reply({ content: 'You must bet a positive amount.', ephemeral: true });
        }

        // Check if user has enough of the resource
        const [user] = await User.findOrCreate({ where: { discordId: userId } });
        const [inventory] = await Inventory.findOrCreate({ where: { userId: user.id } });

        if (inventory[resource] < amount) {
            return interaction.reply({ content: `You do not have enough ${resource} to bet.`, ephemeral: true });
        }

        // Mark the user as having an active bet
        activeBets.set(userId, true);

        // Create the embed for betting
        const embed = new EmbedBuilder()
            .setColor('#0099ff')
            .setTitle('Coin Flip!')
            .setThumbnail(interaction.user.displayAvatarURL()) // Add the user's avatar as a thumbnail
            .setDescription(`You are betting **${amount}** ${getEmojiForResource(resource)}. React with ⚪ for heads or ⚫ for tails.`);

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

            // Update the inventory based on the result
            if (isWin) {
                inventory[resource] += amount;
                embed.setDescription(`${getRandomWinMessage()} **+${amount}** ${getEmojiForResource(resource)}`);
                embed.setColor('#00ff00');
            } else {
                inventory[resource] -= amount;
                embed.setDescription(`${getRandomLoseMessage()} **-${amount}** ${getEmojiForResource(resource)}`);
                embed.setColor('#ff0000');
            }

            await inventory.save();
            await message.edit({ embeds: [embed] });

            // Remove the user from the active bets map
            activeBets.delete(userId);

            collector.stop();
        });

        collector.on('end', (collected, reason) => {
            if (reason === 'time') {
                embed.setDescription('Time is up! You did not react in time.');
                embed.setFooter({ text: 'No changes to your inventory.' });
                message.edit({ embeds: [embed] });

                // Remove the user from the active bets map
                activeBets.delete(userId);
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
    const winMessages = ['You won!', 'Congratulations!', 'W moment!', 'GG!', 'Lets Gooo!'];
    return winMessages[Math.floor(Math.random() * winMessages.length)];
}

// Helper function to get a random lose message
function getRandomLoseMessage() {
    const loseMessages = ['You Lose!', 'Rip Bozo!', 'Skill issue💀', 'Sucks to Suck!', 'L '];
    return loseMessages[Math.floor(Math.random() * loseMessages.length)];
}
