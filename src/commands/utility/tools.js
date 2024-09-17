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
            await interaction.deferReply();

            // Fetch the user's data
            const user = await User.findOne({ where: { discordId } });

            if (!user) {
                return interaction.editReply('User not found.');
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
                .setFooter({ text: `Tools increase resources obtained and decrease cooldowns` });

            // Metal Axe
            if (tools.metalAxe) {
                embed.addFields({ name: '🪓 Metal Axe', value: `Durability: ${tools.metalAxeDurability}/50`, inline: true });
            } else {
                embed.addFields({ name: '🪓 Metal Axe', value: 'Not owned', inline: true });
            }

            // Metal Pickaxe
            if (tools.metalPickaxe) {
                embed.addFields({ name: '⛏️ Metal Pickaxe', value: `Durability: ${tools.metalPickaxeDurability}/50`, inline: true });
            } else {
                embed.addFields({ name: '⛏️ Metal Pickaxe', value: 'Not owned', inline: true });
            }

            // Fishing Rod
            if (tools.fishingRod) {
                embed.addFields({ name: '🎣 Fishing Rod', value: `Durability: ${tools.fishingRodDurability}/100`, inline: true });
            } else {
                embed.addFields({ name: '🎣 Fishing Rod', value: 'Not owned', inline: true });
            }

            // Gloves
            if (tools.gloves) {
                embed.addFields({ name: '🧤 Gloves', value: `Durability: ${tools.glovesDurability}/100`, inline: true });
            } else {
                embed.addFields({ name: '🧤 Gloves', value: 'Not owned', inline: true });
            }

            // Dagger
            if (tools.dagger) {
                embed.addFields({ name: '🗡️ Dagger', value: `Durability: ${tools.daggerDurability}/100`, inline: true });
            } else {
                embed.addFields({ name: '🗡️ Dagger', value: 'Not owned', inline: true });
            }

            // Reply to the interaction with the embed
            return interaction.editReply({ embeds: [embed] });
        } catch (error) {
            console.error('Error fetching tools:', error);
            return interaction.editReply('There was an error fetching your tools.');
        }
    },
};
