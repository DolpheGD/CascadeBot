const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('chop')
        .setDescription('Collect 2-5 wood'),

    async execute(interaction) {
        const cooldown = 20 * 1000; // 20 seconds cooldown
        const userId = interaction.user.id;
        const [user] = await User.findOrCreate({ where: { discordId: userId } });
        
        const lastChop = user.lastChop || 0;
        const now = Date.now();

        if (now - lastChop < cooldown) {
            return interaction.reply({ content: `You are chopping too fast! Please wait ${Math.ceil((cooldown - (now - lastChop)) / 1000)} more seconds.`, ephemeral: true });
        }

        let wood = Math.floor(Math.random() * 4) + 1; // Random amount of wood between 1 and 5
        user.wood += wood;
        user.lastChop = now;

        // Determine if there's a negative or positive event
        let isNegative = false;
        let isBonus = false;
        let bonusWood = 0;

        if (Math.random() < 0.1 && user.wood >= 10) { // 10% chance of negative event
            isNegative = true;
        } else if (Math.random() < 0.15) { // 15% chance of bonus
            isBonus = true;
            bonusWood = Math.floor(Math.random() * 3) + 4; // Random bonus between 4 and 6
            user.wood += bonusWood;
        }

        await user.save();

        // Create the embed message
        const embed = new EmbedBuilder()
            .setColor(isNegative ? '#ff0000' : '#00ff00')
            .setTitle(isNegative ? 'Failure!' : 'Success!')
            .setDescription(isNegative
                ? `You angered Josh! He stole ${Math.floor(Math.random() * 7) + 1} 🌲.`
                : `You obtained ${wood} 🌲`)
            .setFooter({ text: `Total wood: ${user.wood}` });

        // Add bonus field if applicable
        if (isBonus) {
            embed.addFields({ name: '**Bonus!**', value: `You chopped down a huge tree! **+${bonusWood}** 🌲!`, inline: false });
        }

        return interaction.reply({ embeds: [embed] });
    },
};
