const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('bet')
        .setDescription('Bet an amount of a resource by flipping a coin.')
        .addStringOption(option =>
            option.setName('resource')
                .setDescription('The resource you want to bet (wood, stone, palmLeaves, or gold)')
                .setRequired(true)
                .addChoices(
                    { name: 'Wood', value: 'wood' },
                    { name: 'Stone', value: 'stone' },
                    { name: 'Palm Leaves', value: 'palmLeaves' },
                    { name: 'Gold', value: 'gold' }
                ))
        .addIntegerOption(option =>
            option.setName('amount')
                .setDescription('The amount of the resource you want to bet')
                .setRequired(true)),

    async execute(interaction) {
        const resource = interaction.options.getString('resource');
        const amount = interaction.options.getInteger('amount');
        const userId = interaction.user.id;

        // Valid resources
        const validResources = ['wood', 'stone', 'palmLeaves', 'gold'];
        if (!validResources.includes(resource)) {
            return interaction.reply({ content: 'Invalid resource. Please choose from wood, stone, palmLeaves, or gold.', ephemeral: true });
        }

        // Check if user has enough of the resource
        const [user] = await User.findOrCreate({ where: { discordId: userId } });
        const [inventory] = await Inventory.findOrCreate({ where: { userId: user.id } });

        if (inventory[resource] < amount) {
            return interaction.reply({ content: `You do not have enough ${resource} to bet.`, ephemeral: true });
        }

        // Create the embed for betting
        const embed = new EmbedBuilder()
            .setColor('#0099ff')
            .setTitle('Coin Flip!')
            .setDescription(`You are betting **${amount}** ${resource}. React with ⚪ for heads or ⚫ for tails.`);

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
                embed.setDescription(`You won! **+${amount}** ${getEmojiForResource(resource)}`);
                embed.setColor('#00ff00');
            } else {
                inventory[resource] -= amount;
                embed.setDescription(`Rip Bozo! **-${amount}** ${getEmojiForResource(resource)}`);
                embed.setColor('#ff0000');
            }

            await inventory.save();
            await message.edit({ embeds: [embed] });

            collector.stop();
        });

        collector.on('end', (collected, reason) => {
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
        case 'gold': return '🏅';
        default: return '';
    }
}
