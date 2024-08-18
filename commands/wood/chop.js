const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('chop')
        .setDescription('Chop 2-5 wood'),

    async execute(interaction) {
        const cooldown = 20 * 1000; // 20 seconds cooldown
        const userId = interaction.user.id;
        const username = interaction.user.username; // Get the username

        // Create or find the user and ensure the username is set
        const [user] = await User.findOrCreate({
            where: { discordId: userId },
            defaults: {
                username: username, // Set the username here
            }
        });

        // Create or find the inventory
        const [inventory] = await Inventory.findOrCreate({
            where: { userId: user.id },
            defaults: {
                wood: 0,
                stone: 0,
                palmLeaves: 0,
                gold: 0,
                rope: 0 // Initialize rope to 0
            }
        });

        // Extract cooldown
        const lastChop = user.lastChop || 0;
        const now = Date.now();

        // Check for cooldown
        if (now - lastChop < cooldown) {
            return interaction.reply({
                content: `You are chopping too fast! Please wait ${Math.ceil((cooldown - (now - lastChop)) / 1000)} more seconds.`,
                ephemeral: true
            });
        }

        // Update wood
        let wood = Math.floor(Math.random() * 4) + 1; // Random amount of wood between 1 and 5
        inventory.wood += wood;

        // Determine if there's a negative or positive event
        let isNegative = false;
        let isBonus = false;
        let bonusWood = 0;
        let stolenWood = 0;
        let palmLeaves = 0;
        let rope = 0;

        if (Math.random() < 0.1 && inventory.wood >= 6) { // 10% chance of negative event
            isNegative = true;
            stolenWood = Math.floor(Math.random() * 3) + 1;
            inventory.wood -= stolenWood;
        } else {
            if (Math.random() < 0.15) { // 15% chance of bonus
                isBonus = true;
                bonusWood = Math.floor(Math.random() * 3) + 4; // Random bonus between 4 and 6
                inventory.wood += bonusWood;
            }
            if (Math.random() < 0.4) { // 40% chance of getting palm leaves
                palmLeaves = Math.floor(Math.random() * 2) + 1; // Random 1-2 palm leaves
                inventory.palmLeaves += palmLeaves;
            }
            if (Math.random() < 0.04) { // 4% chance of getting rope
                rope = Math.floor(Math.random() * 2) + 1; // Random 1-2 rope
                inventory.rope += rope;
            }
        }

        // Save changes
        user.lastChop = now;
        await inventory.save();
        await user.save();

        // Create the embed message
        const embed = new EmbedBuilder()
            .setColor(isNegative ? '#ff0000' : '#00ff00')
            .setTitle(isNegative ? 'Failure!' : 'Success!')
            .setDescription(isNegative
                ? `You angered Josh! **-${stolenWood}** 🪵.`
                : `You obtained ${wood} 🪵`)
            .setFooter({ text: `Total wood: ${inventory.wood}` });

        // Add bonus field if applicable
        if (isBonus) {
            embed.addFields({ name: '**Bonus!**', value: `You chopped down a huge tree! **+${bonusWood}** 🪵!`, inline: false });
        }

        // Add palm leaves field if applicable
        if (palmLeaves > 0) {
            embed.addFields({ name: '**Bonus!**', value: `You picked up some huge leaves! **+${palmLeaves}** 🍃!`, inline: false });
        }

        // Add rope field if applicable
        if (rope > 0) {
            embed.addFields({ name: '**Bonus!**', value: `You found some leftover rope! **+${rope}** 🪢!`, inline: false });
        }

        return interaction.reply({ embeds: [embed] });
    },
};
