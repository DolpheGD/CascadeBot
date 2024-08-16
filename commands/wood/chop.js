const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('chop')
        .setDescription('Collect 2-5 wood'),

    async execute(interaction) {
        const cooldown = 20 * 1000; // 10 seconds cooldown
        const userId = interaction.user.id;
        const user = await User.findOrCreate({ where: { discordId: userId } });
        
        const lastChop = user[0].lastChop || 0;
        const now = Date.now();

        if (now - lastChop < cooldown) {
            return interaction.reply({ content: `You are chopping too fast! Please wait ${Math.ceil((cooldown - (now - lastChop)) / 1000)} more seconds.`, ephemeral: true });
        }

        const wood = Math.floor(Math.random() * 3) + 2;
        user[0].wood += wood;
        user[0].lastChop = now;
        await user[0].save();

        // embedded response
        const embed = new EmbedBuilder()
            .setColor('#00ff00')
            .setTitle('Success!')
            .addFields(
                { name: 'Wood Obtained', value: `${wood} 🌲`, inline: false } // Add a field with emoji
            )

        return interaction.reply({embeds: [embed]});
    },
};