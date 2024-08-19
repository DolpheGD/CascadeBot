const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const Tool = require('../../models/Tool');
const User = require('../../models/User');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('tools')
        .setDescription('Displays the tools you have and their durability'),
        
    async execute(interaction) {
        const discordId = interaction.user.id;

        try {
            // Fetch the user's data
            const user = await User.findOne({ where: { discordId } });

            if (!user) {
                return interaction.reply('User not found.');
            }

            // Fetch or create the user's tools
            let tools = await Tool.findOne({ where: { userId: user.id } });

            if (!tools) {
                tools = await Tool.create({ userId: user.id });
            }

            // Construct the embed
            const embed = new EmbedBuilder()
                .setTitle(`${interaction.user.username}'s Tools`)
                .setThumbnail(interaction.user.displayAvatarURL({ dynamic: true }))
                .setColor('#0099ff')
                .setFooter({ text: `Tools increase resources obtained and decrease cooldowns`});

            if (tools.metalAxe) {
                embed.addFields({ name: '🪓 Metal Axe', value: `Durability: ${tools.metalAxeDurability}/50`, inline: true });
            } else {
                embed.addFields({ name: '🪓 Metal Axe', value: 'Not owned', inline: true });
            }

            if (tools.metalPickaxe) {
                embed.addFields({ name: '⛏️ Metal Pickaxe', value: `Durability: ${tools.metalPickaxeDurability}/50`, inline: true });
            } else {
                embed.addFields({ name: '⛏️ Metal Pickaxe', value: 'Not owned', inline: true });
            }

            // Reply to the interaction with the embed
            return interaction.reply({ embeds: [embed] });
        } catch (error) {
            console.error('Error fetching tools:', error);
            return interaction.reply('There was an error fetching your tools.');
        }
    },
};
