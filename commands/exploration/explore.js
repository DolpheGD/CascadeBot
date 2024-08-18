const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');

const events = [
    {
        id: 1,
        description: "You spot Josh near a campfire",
        choices: [
            { emoji: '1️⃣', text: 'Approach Josh', result: async (interaction, inventory) => {
                const chance = Math.random();
                let resultMessage = '';
                let embedColor = '#00ff00'; // Default to green

                if (chance < 0.4) { // 40% chance for ambush
                    let resourceFound = false;
                    resultMessage = 'Josh ambushes you and steals your resources!\n';
                    
                    while (!resourceFound) {
                        const resources = ['wood', 'stone', 'palmLeaves'];
                        const resource = resources[Math.floor(Math.random() * resources.length)];
                        const amount = Math.floor(Math.random() * 5) + 1; // 1 to 5

                        if (inventory[resource] >= amount) {
                            inventory[resource] -= amount;
                            await inventory.save();
                            resultMessage += `-${amount} ${resource === 'wood' ? '🪵' : resource === 'stone' ? '🪨' : '🌿'}`;
                            resourceFound = true;
                        }

                        if (resources.every(r => inventory[r] < 1)) {
                            resultMessage = 'Josh ambushes you but you don\'t have enough resources to lose.';
                            resourceFound = true;
                        }
                    }
                    embedColor = '#ff0000'; // Red color for ambush
                } else {
                    const woodGained = Math.floor(Math.random() * 4) + 3;
                    inventory.wood += woodGained;
                    await inventory.save();
                    resultMessage = `You approach Josh and he runs away! You collect the leftover wood.\n**+${woodGained}** 🪵`;
                }

                return { message: resultMessage, color: embedColor };
            }},
            { emoji: '2️⃣', text: 'Leave', result: () => ({ message: 'You run away!\n(no change in resources)', color: '#00ff00' })}
        ],
        imageUrl: 'https://cdn.discordapp.com/attachments/704530416475832342/1274296689481482343/JOSHCAMPFIRE.png?ex=66c1bcc6&is=66c06b46&hm=05c5249f2ec3bc738a830ae66aa757b12de4053c1f629707087eee11fe466362&'
    },
        {
            id: 2,
            description: "You are about to collab with Dolphe, what do you contribute?",
            choices: [
                    {
                        emoji: '1️⃣', 
                        text: 'Give Dolphe 5 🪵', 
                        resource: 'wood', 
                        cost: 5, 
                        result: async (interaction, inventory) => {
                            if (inventory.wood < 5) {
                                return await handleDolpheSteal(inventory);
                            }
                    
                            inventory.wood -= 5;
                            await inventory.save();
                            return { 
                                message: `Dolphe is actually doing a YouTube video and gives you resources for helping him out!\n**+8** 🪵`, 
                                color: '#00ff00' 
                            };
                        }
                    },
                    {
                        emoji: '2️⃣', 
                        text: 'Give Dolphe 5 🪨', 
                        resource: 'stone', 
                        cost: 5, 
                        result: async (interaction, inventory) => {
                            if (inventory.stone < 5) {
                                return await handleDolpheSteal(inventory);
                            }
                    
                            inventory.stone -= 5;
                            await inventory.save();
                            return { 
                                message: `Dolphe is actually doing a YouTube video and gives you resources for helping him out!\n**+8** 🪨`, 
                                color: '#00ff00' 
                            };
                        }
                    },
                    {
                        emoji: '3️⃣', 
                        text: 'Give Dolphe 5 🌿', 
                        resource: 'palmLeaves', 
                        cost: 5, 
                        result: async (interaction, inventory) => {
                            if (inventory.palmLeaves < 5) {
                                return await handleDolpheSteal(inventory);
                            }
                    
                            inventory.palmLeaves -= 5;
                            await inventory.save();
                            return { 
                                message: `Dolphe is actually doing a YouTube video and gives you resources for helping him out!\n**+8** 🌿`, 
                                color: '#00ff00' 
                            };
                        }
                    },
                    {
                        emoji: '4️⃣', 
                        text: 'Give Dolphe nothing!!', 
                        result: async (interaction, inventory) => await handleDolpheSteal(inventory)
                    }
                    
            ],
            imageUrl: 'https://cdn.discordapp.com/attachments/704530416475832342/1274298451038961774/DOLPHEVENT.png?ex=66c1be6a&is=66c06cea&hm=68f0a3c722745dd10bbabb82880416d4a1c7ce1d16424bcdf52b0ca7fcf3ad34&'
        },
    {
        id: 3,
        description: "You come across Xender, a shady dealer. He requests 1 🪵, 1 🪨, and 1 🌿 for a 10% chance to win 10 🏅",
        choices: [
            { emoji: '1️⃣', text: 'Accept the deal', result: async (interaction, inventory) => {
                if (inventory.wood >= 1 && inventory.stone >= 1 && inventory.palmLeaves >= 1) {
                    inventory.wood -= 1;
                    inventory.stone -= 1;
                    inventory.palmLeaves -= 1;
                    await inventory.save();

                    const winChance = Math.random();
                    let resultMessage = 'You accepted the deal.';

                    if (winChance < 0.1) { // 10% chance to win 10 gold
                        inventory.gold = (inventory.gold || 0) + 10;
                        await inventory.save();
                        resultMessage += '\nCongratulations! You won!\n**+10** 🏅';
                        return { message: resultMessage, color: '#00ff00' }; // Green color for winning
                    } else {
                        resultMessage += '\nSorry, you didn\'t win anything.';
                        return { message: resultMessage, color: '#ff0000' }; // Red color for losing
                    }
                } else {
                    return { message: 'You do not have enough resources to accept the deal.', color: '#ff0000' }; // Red color for insufficient resources
                }
            }},
            { emoji: '2️⃣', text: 'Leave', result: () => ({ message: 'You leave Xender and continue your exploration.', color: '#00ff00' })}
        ],
        imageUrl: 'https://cdn.discordapp.com/attachments/704530416475832342/1274325004007374921/XENDERCRACKPIPE.png?ex=66c1d724&is=66c085a4&hm=3917ed9d266c67b65fc2186bc45da7fe5a7d35b78250a0dd497bdfc4b14dd828&'
    },
    {
        id: 4,
        description: "You meet Rex, an old crafter. He offers to craft your palm leaves into rope.",
        choices: [
            { 
                emoji: '1️⃣', 
                text: 'Craft 4 🌿 into 2 🪢', 
                result: async (interaction, inventory) => {
                    if (inventory.palmLeaves >= 4) {
                        inventory.palmLeaves -= 4;
                        inventory.rope = (inventory.rope || 0) + 2;
                        await inventory.save();
                        return { message: 'Rex crafts 2 🪢 for you.', color: '#00ff00' };
                    } else {
                        return { message: 'You don’t have enough palm leaves!', color: '#ff0000' };
                    }
                }
            },
            { 
                emoji: '2️⃣', 
                text: 'Craft 8 🌿 into 4 🪢', 
                result: async (interaction, inventory) => {
                    if (inventory.palmLeaves >= 8) {
                        inventory.palmLeaves -= 8;
                        inventory.rope = (inventory.rope || 0) + 4;
                        await inventory.save();
                        return { message: 'Rex crafts 4 🪢 for you.', color: '#00ff00' };
                    } else {
                        return { message: 'You don’t have enough palm leaves!', color: '#ff0000' };
                    }
                }
            },
            { 
                emoji: '3️⃣', 
                text: 'Leave', 
                result: () => ({ message: 'You decide to leave Rex and continue your exploration.', color: '#00ff00' })
            },
            { 
                emoji: '4️⃣', 
                text: 'Ambush Rex', 
                result: async (interaction, inventory) => {
                    const chance = Math.random();
                    let resultMessage = '';
                    let embedColor = '#00ff00'; 
    
                    if (chance < 0.1) { // 10% chance you overpower Rex
                        inventory.gold = (inventory.gold || 0) + 5;
                        inventory.rope = (inventory.rope || 0) + 5;
                        await inventory.save();
                        resultMessage = '**You overpower Rex and defeat him!**\n**+5** 🏅\n**+5** 🪢';
                    } else if (chance < 0.75) { // 65% chance you and Rex have a scuffle
                        resultMessage = '**You and Rex have a scuffle, tossing your items around!**\n';
                        const resources = ['wood', 'stone', 'palmLeaves'];
                        resources.forEach(async (resource) => {
                            if (inventory[resource] > 0) {
                                const amount = Math.min(inventory[resource], 1);
                                inventory[resource] -= amount;
                                resultMessage += `-${amount} ${resource === 'wood' ? '🪵' : resource === 'stone' ? '🪨' : '🌿'}`;
                            }
                        });
                        await inventory.save();
                        embedColor = '#ffa500'; // Orange color for scuffle
                    } else { // 25% chance Rex overpowers you
                        resultMessage = '**Rex overpowers you and loots your resources!**\n';
                        const resources = ['wood', 'stone', 'palmLeaves'];
                        resources.forEach(async (resource) => {
                            if (inventory[resource] > 0) {
                                const amount = Math.min(inventory[resource], 5);
                                inventory[resource] -= amount;
                                resultMessage += `-${amount} ${resource === 'wood' ? '🪵' : resource === 'stone' ? '🪨' : '🌿'}`;
                            }
                        });
                        await inventory.save();
                        embedColor = '#ff0000'; // Red color for Rex overpowering
                    }
    
                    return { message: resultMessage, color: embedColor };
                }
            }
        ],
        imageUrl: 'https://cdn.discordapp.com/attachments/704530416475832342/1274572311445635173/REXEVENT.png?ex=66c2bd77&is=66c16bf7&hm=51b48f281e43a17933bde33d083b48f70d8ea1dbe63c55d276a0ba0a0af0923e&'
    }
    
];

async function handleDolpheSteal(inventory) {
    const resources = ['wood', 'stone', 'palmLeaves'];
    let resultMessage = 'Dolphe gets mad and takes your resources!\n';
    let resourceFound = false;

    while (!resourceFound) {
        const resource = resources[Math.floor(Math.random() * resources.length)];
        const amount = Math.floor(Math.random() * 3) + 1; // 1 to 3

        if (inventory[resource] >= amount) {
            inventory[resource] -= amount;
            await inventory.save();
            resultMessage += `-${amount} ${resource === 'wood' ? '🪵' : resource === 'stone' ? '🪨' : '🌿'}`;
            resourceFound = true;
        }

        if (resources.every(r => inventory[r] < 1)) {
            resultMessage = 'Dolphe gets mad but you don\'t have enough resources to lose.';
            resourceFound = true;
        }
    }

    return { message: resultMessage, color: '#ff0000' }; // Red color for Dolphe stealing
}

module.exports = {
    data: new SlashCommandBuilder()
        .setName('explore')
        .setDescription('Explore and make choices to gain or lose resources.'),
    
    async execute(interaction) {
        const userId = interaction.user.id;

        try {
            // Find or create the user and their inventory
            const [user] = await User.findOrCreate({ where: { discordId: userId } });
            const [inventory] = await Inventory.findOrCreate({ where: { userId: user.id } });

            // Cooldown check
            const now = Date.now();
            const cooldown = 70 * 1000; // 70 seconds
            const lastExplore = user.lastExplore || 0;

            if (now - lastExplore < cooldown) {
                const remainingTime = Math.ceil((cooldown - (now - lastExplore)) / 1000);
                return interaction.reply({ content: `Please wait ${remainingTime} seconds before exploring again.`, ephemeral: true });
            }

            // Update the lastExplore time
            user.lastExplore = now;
            await user.save();

            // Choose a random event
            const event = events[Math.floor(Math.random() * events.length)];

            // Create an embed for the event
            const embed = new EmbedBuilder()
                .setColor('#0099ff')
                .setTitle('Exploration Event!')
                .setDescription(event.description)
                .setImage(event.imageUrl)
                .addFields(event.choices.map(choice => ({ name: choice.emoji, value: choice.text, inline: true })))
                .setFooter({ text: 'React with the number corresponding to your choice.' });

            // Send the embed and add reactions
            const message = await interaction.reply({ embeds: [embed], fetchReply: true });
            event.choices.forEach(choice => message.react(choice.emoji));

            // Set up a reaction collector
            const filter = (reaction, user) => event.choices.map(choice => choice.emoji).includes(reaction.emoji.name) && user.id === interaction.user.id;
            const collector = message.createReactionCollector({ filter, time: 60000 }); // 1 minute

            collector.on('collect', async (reaction) => {
                const choice = event.choices.find(c => c.emoji === reaction.emoji.name);
                const { message: resultMessage, color: embedColor } = await choice.result(interaction, inventory);

                const resultEmbed = new EmbedBuilder()
                    .setColor(embedColor)
                    .setTitle('Event Result')
                    .setDescription(resultMessage)
                    .setImage(event.imageUrl);

                await message.edit({ embeds: [resultEmbed] });

                collector.stop();
            });

            collector.on('end', (collected, reason) => {
                if (reason === 'time') {
                    const timeoutEmbed = new EmbedBuilder()
                        .setColor('#ff0000')
                        .setTitle('Timeout')
                        .setDescription('You did not react in time. Please use the command again.')
                        .setImage(event.imageUrl);

                    message.edit({ embeds: [timeoutEmbed] });
                }
            });

        } catch (error) {
            console.error('Error executing explore command:', error);
            return interaction.reply({ content: 'An error occurred while executing the command. Please try again later.', ephemeral: true });
        }
    },
};