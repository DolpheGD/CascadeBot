const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const Quest = require('../../models/Quest');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');
const { Op } = require('sequelize');

const questTypes = ['mine'];
//const questTypes = ['chop', 'mine', 'forage', 'explore'];
const questCooldown = 2 * 60 * 60 * 1000; // 2 hours in milliseconds

module.exports = {
    data: new SlashCommandBuilder()
        .setName('quest')
        .setDescription('Get or view your quests'),
    async execute(interaction) {
        const userId = interaction.user.id;

        // Find or create the user
        const [user] = await User.findOrCreate({ where: { discordId: userId } });

        // Find the user's active quest
        const activeQuest = await Quest.findOne({
            where: {
                userId: user.id, // Use User model's id
                isCompleted: false,
            }
        });

        if (activeQuest) {
            // Display current quest progress
            const embed = new EmbedBuilder()
                .setColor('#00ff00')
                .setTitle('Current Quest')
                .setDescription(`Use /${activeQuest.questType} 5 times successfully.`)
                .addFields(
                    { name: 'Progress', value: `${activeQuest.progress || 0}/5`, inline: true }
                )
                .setThumbnail(interaction.user.displayAvatarURL());

            // Check if the user can claim a new quest after completing the current one
            const timeLeft = user.lastQuest + questCooldown - Date.now();
            if (timeLeft > 0) {
                embed.setFooter({ text: `You can claim another quest in ${Math.ceil(timeLeft / (60 * 1000))} minutes.` });
            } else {
                embed.setFooter({ text: 'You can claim another quest after completing this one.' });
            }

            return interaction.reply({ embeds: [embed] });
        }

        // Check if the user is eligible for a new quest
        const timeSinceLastQuest = Date.now() - user.lastQuest;
        if (timeSinceLastQuest < questCooldown) {
            const timeLeft = Math.ceil((questCooldown - timeSinceLastQuest) / (60 * 1000));
            return interaction.reply({ content: `You can claim a new quest in ${timeLeft} minutes.`, ephemeral: true });
        }

        // Assign a new random quest
        const questType = questTypes[Math.floor(Math.random() * questTypes.length)];
        await Quest.create({
            userId: user.id, // Use User model's id
            questType: questType,
            isCompleted: false,
            progress: 0, // Initialize progress
            startTime: new Date(),
        });

        // Update the user's lastQuest time
        user.lastQuest = Date.now();
        await user.save();

        const embed = new EmbedBuilder()
            .setColor('#00ff00')
            .setTitle('New Quest Assigned!')
            .setDescription(`Use /${questType} 5 times successfully.`)
            .setThumbnail(interaction.user.displayAvatarURL())
            .setFooter({ text: 'You can claim another quest after completing this one.' });

        await interaction.reply({ embeds: [embed] });
    },

    async trackQuestProgress(discordId, questType, interaction) {
        console.log('Tracking quest...');
        console.log(`DiscordID: ${discordId}, QuestType: ${questType}`);
        
        // Find the user by their Discord ID
        const user = await User.findOne({ where: { discordId: discordId } });
        
        if (!user) {
            console.log('User not found. DiscordID:', discordId);
            return;
        }
        
        // Find the quest with the correct userId and questType
        const quest = await Quest.findOne({
            where: {
                userId: user.id, // Use the user model's id
                questType: questType,
                isCompleted: false,
            }
        });
        
        if (quest) {
            quest.progress = (quest.progress || 0) + 1;
            
            let description = '';
            
            if (quest.progress >= 5) {
                quest.isCompleted = true;
                await quest.save();
                
                const rewards = await giveQuestRewards(user.id);
                description = `Congratulations! You have completed the quest: Use /${questType} 5 times successfully.`;
                
                // Format the rewards
                description += `\n\nYou received:\n${rewards.join('\n')}`;
                
            } else {
                await quest.save();
                description = `Progress: ${quest.progress}/5 for ${questType} quest.`;
            }
    
            return description;
        } else {
            console.log('No active quest found. DiscordID:', discordId, 'QuestType:', questType);
            return 'No active quest found.';
        }
    }
};

// Function to give rewards for completing the quest
async function giveQuestRewards(userId) {
    const [inventory] = await Inventory.findOrCreate({ where: { userId: userId } });

    const rewards = [
        { resource: 'wood', amount: 20, emoji: '🪵' },
        { resource: 'stone', amount: 20, emoji: '🪨' },
        { resource: 'palmLeaves', amount: 20, emoji: '🍃' },
        { resource: 'copper', amount: 20, emoji: '🔶' },
        { resource: 'gold', amount: 5, emoji: '✨' }
    ];

    // Shuffle and pick two rewards
    rewards.sort(() => Math.random() - 0.5);
    const selectedRewards = rewards.slice(0, 2);

    const rewardDescriptions = selectedRewards.map(reward => {
        inventory[reward.resource] += reward.amount;
        return `+${reward.amount} ${reward.emoji}`;
    });

    await inventory.save();

    return rewardDescriptions;
}