const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');

module.exports = {
    data: new SlashCommandBuilder()
        .setName('mine')
        .setDescription('Mine for 1-3 stone'),

    async execute(interaction) {
        const cooldown = 60 * 1000; // 60 seconds cooldown
        const userId = interaction.user.id;

        try {
            // Find or create the user
            const [user] = await User.findOrCreate({
                where: { discordId: userId },
                defaults: {
                    username: interaction.user.username, // Set the username here
                }
            });

            // Find or create the inventory for the user
            const [inventory] = await Inventory.findOrCreate({
                where: { userId: user.id }, // Use user.id here
                defaults: {
                    wood: 0,
                    stone: 0,
                    palmLeaves: 0,
                    gold: 0
                }
            });

            const lastMine = user.lastMine || 0;
            const now = Date.now();

            if (now - lastMine < cooldown) {
                return interaction.reply({
                    content: `You are mining too fast! Please wait ${Math.ceil((cooldown - (now - lastMine)) / 1000)} more seconds.`,
                    ephemeral: true
                });
            }

            let stone = Math.floor(Math.random() * 3) + 1; // Random amount of stone between 1 and 3
            let gold = Math.random() < 0.1 ? 1 : 0; // 10% chance of getting 1 gold
            inventory.stone += stone;
            inventory.gold += gold;
            user.lastMine = now;

            // Save the inventory and user cooldown
            await inventory.save();
            await user.save();

            const embed = new EmbedBuilder()
                .setColor('#00ff00')
                .setTitle('Success!')
                .setDescription(`You obtained ${stone} 🪨`)
                .setFooter({ text: `Total stone: ${inventory.stone}` });

            if (gold > 0) {
                embed.addFields({ name: 'Bonus!', value: `You mined something shiny! **+${gold}** 🏅`, inline: false });
            }

            return interaction.reply({ embeds: [embed] });
        } catch (error) {
            console.error('Error mining stone:', error);
            return interaction.reply({ content: 'An error occurred while mining. Please try again later.', ephemeral: true });
        }
    },
};
