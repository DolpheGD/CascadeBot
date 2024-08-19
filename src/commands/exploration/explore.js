const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const User = require('../../models/User');
const Inventory = require('../../models/Inventory');
const Tool = require('../../models/Tool'); // Adjust the path as needed

const resourceEmojiMap = {
    wood: '🪵',
    stone: '🪨',
    palmLeaves: '🍃',
    copper: '🔶',
    rope: '🪢',
    gold: '✨',
    ruby: '♦️'
};







//------------------------------------------------
// EVENTS
//------------------------------------------------
const events = [
    {
        id: 1,
        description: "You spot Josh near a campfire",
        choices: [
            {
                emoji: '1️⃣',
                text: 'Ambush Josh',
                result: async (interaction, inventory) => {
                    const chance = Math.random();
                    let resultMessage = '';
                    let embedColor = '#00ff00'; // Default to green
    
                    if (chance < 0.4) { // 40% chance for ambush
                        let resourceFound = false;
                        resultMessage = 'Josh beats you up and steals your resources!\n';
    
                        while (!resourceFound) {
                            const resources = ['wood', 'stone', 'palmLeaves'];
                            const resource = resources[Math.floor(Math.random() * resources.length)];
                            const amount = Math.floor(Math.random() * 5) + 1; // 1 to 5
    
                            if (inventory[resource] >= amount) {
                                inventory[resource] -= amount;
                                await inventory.save();
                                resultMessage += `**-${amount}** ${resource === 'wood' ? '🪵' : resource === 'stone' ? '🪨' : '🌿'}`;
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
                        resultMessage = `You ambush Josh and he flees! You collect the leftover wood.\n**+${woodGained}** 🪵`;
                    }
    
                    return { message: resultMessage, color: embedColor };
                }
            },
            {
                emoji: '2️⃣',
                text: 'Barter 2✨ for wood',
                result: async (interaction, inventory) => {
                    let resultMessage = '';
                    let embedColor = '#00ff00'; // Default to green
    
                    if (inventory.gold >= 2) {
                        inventory.gold -= 2;
                        const chance = Math.random();
    
                        if (chance < 0.95) { // 95% chance of getting wood
                            const woodGained = Math.floor(Math.random() * 8) + 5; // 5 to 12 wood
                            inventory.wood += woodGained;
                            resultMessage = `Josh accepts your gold and gives you some spare wood!\n**+${woodGained}** 🪵`;
                        } else { // 5% chance of getting scammed
                            resultMessage = 'Josh takes your gold and runs away!';
                            embedColor = '#ff0000'; // Red color for scam
                        }
                    } else {
                        resultMessage = 'You don’t have enough gold to barter!';
                        embedColor = '#ff0000'; // Red color for failure
                    }
    
                    await inventory.save();
                    return { message: resultMessage, color: embedColor };
                }
            },
            {
                emoji: '3️⃣',
                text: 'Barter 2♦️ for wood',
                result: async (interaction, inventory) => {
                    let resultMessage = '';
                    let embedColor = '#00ff00'; // Default to green
    
                    if (inventory.ruby >= 2) {
                        inventory.ruby -= 2;
                        const chance = Math.random();
    
                        if (chance < 0.98) { // 98% chance of getting a huge stack of wood
                            const woodGained = Math.floor(Math.random() * 61) + 50; // 50 to 110 wood
                            inventory.wood += woodGained;
                            resultMessage = `Josh accepts your rubies and gives you a huge stack of wood!\n**+${woodGained}** 🪵`;
                        } else { // 2% chance of getting scammed
                            resultMessage = 'Josh takes your rubies and runs away!';
                            embedColor = '#ff0000'; // Red color for scam
                        }
                    } else {
                        resultMessage = 'You don’t have enough rubies to barter!';
                        embedColor = '#ff0000'; // Red color for failure
                    }
    
                    await inventory.save();
                    return { message: resultMessage, color: embedColor };
                }
            },
            {
                emoji: '4️⃣',
                text: 'Leave',
                result: () => ({ message: 'You run away!', color: '#0099ff' })
            }
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
                                message: `Dolphe is actually doing a YouTube video and gives you resources for helping him out!\n**+3** 🪵`, 
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
                                message: `Dolphe is actually doing a YouTube video and gives you resources for helping him out!\n**+3** 🪨`, 
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
                                message: `Dolphe is actually doing a YouTube video and gives you resources for helping him out!\n**+3** 🌿`, 
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
        description: "You come across Xender, a shady dealer. He requests 1 🪵, 1 🪨, and 1 🌿 for a 10% chance to win 10 ✨",
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
                        resultMessage += '\nCongratulations! You won!\n**+10** ✨';
                        return { message: resultMessage, color: '#00ff00' }; // Green color for winning
                    } else {
                        resultMessage += '\nSorry, you didn\'t win anything.';
                        return { message: resultMessage, color: '#ff0000' }; // Red color for losing
                    }
                } else {
                    return { message: 'You do not have enough resources to accept the deal.', color: '#ff0000' }; // Red color for insufficient resources
                }
            }},
            { emoji: '2️⃣', text: 'Leave', result: () => ({ message: 'You leave Xender and continue your exploration.', color: '#0099ff' })}
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
                result: () => ({ message: 'You decide to leave Rex and continue your exploration.', color: '#0099ff' })
            },
            { 
                emoji: '4️⃣', 
                text: 'Ambush Rex', 
                result: async (interaction, inventory) => {
                    const chance = Math.random();
                    let resultMessage = '';
                    let embedColor = '#00ff00'; 
    
                    if (chance < 0.15) { // 15% chance you overpower Rex
                        inventory.gold = (inventory.gold || 0) + 5;
                        inventory.rope = (inventory.rope || 0) + 5;
                        await inventory.save();
                        resultMessage = '**You overpower Rex and defeat him!**\n**+5**✨ **+5**🪢';
                    } else if (chance < 0.75) { // 55% chance you and Rex have a scuffle
                        resultMessage = '**You and Rex have a scuffle, tossing your items around!**\n';
                        const resources = ['wood', 'stone', 'palmLeaves'];
                        resources.forEach(async (resource) => {
                            if (inventory[resource] > 0) {
                                const amount = Math.min(inventory[resource], 1);
                                inventory[resource] -= amount;
                                resultMessage += `**-${amount}** ${resource === 'wood' ? '🪵' : resource === 'stone' ? '🪨' : '🌿'}`;
                            }
                        });
                        await inventory.save();
                        embedColor = '#ffa500'; // Orange color for scuffle
                    } else { // 25% chance Rex overpowers you
                        resultMessage = '**Rex overpowers you and loots your resources!**\n';
                        const resources = ['wood', 'stone', 'palmLeaves'];
                        resources.forEach(async (resource) => {
                            if (inventory[resource] > 0) {
                                const amount = Math.min(inventory[resource], 10);
                                inventory[resource] -= amount;
                                resultMessage += `**-${amount}** ${resource === 'wood' ? '🪵' : resource === 'stone' ? '🪨' : '🌿'}`;
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
    },
    {
        id: 5,
        description: "You meet Duko, an illegal rock dealer. 1 loot rock for **6**🪵 and **3**🪨",
        choices: [
            { emoji: '1️⃣', text: 'Leave', result: () => ({ message: 'You decide to leave Duko and continue your exploration.', color: '#0099ff' })},
            { emoji: '2️⃣', text: 'Buy 1 rock', result: async (interaction, inventory) => await handleRockPurchase(interaction, inventory, 1) },
            { emoji: '3️⃣', text: 'Buy 3 rocks', result: async (interaction, inventory) => await handleRockPurchase(interaction, inventory, 3) },
            { emoji: '4️⃣', text: 'Buy 5 rocks', result: async (interaction, inventory) => await handleRockPurchase(interaction, inventory, 5) },
            { emoji: '5️⃣', text: 'Buy 10 rocks', result: async (interaction, inventory) => await handleRockPurchase(interaction, inventory, 10) },
            { emoji: '6️⃣', text: 'Buy 20 rocks', result: async (interaction, inventory) => await handleRockPurchase(interaction, inventory, 20) }
        ],
        imageUrl: 'https://cdn.discordapp.com/attachments/704530416475832342/1274616296985723056/DUKOEVENTROCKSD.png?ex=66c2e66e&is=66c194ee&hm=806de9a45039aef475a2eb79f82e05a62d7dedf1973aeff36c52a2d7527f71c0&'
    },
    {
        id: 6,
        description: "You encounter Triv, a feared swordsman, who challenges you to a 1v1 battle.",
        imageUrl: "https://cdn.discordapp.com/attachments/704530416475832342/1274674180419489822/1v1Triv.png?ex=66c31c56&is=66c1cad6&hm=566990eab2e9890a657e0f2c018f84c724f4a9776bd0ea3bb684af8f13b62df6&",
        choices: [
            {
                emoji: '1️⃣',
                text: 'Flee',
                async result(interaction, inventory) {
                    const resources = ['wood', 'stone', 'copper'];
                    let resultMessage = "You flee from Triv, but you drop some resources in the process!\n";
                    
                    // Track resource losses
                    resources.forEach(resource => {
                        if (inventory[resource] > 0) {
                            inventory[resource] -= 1;
                            resultMessage += `-1 ${resourceEmojiMap[resource]}\n`;
                        }
                    });
    
                    await inventory.save();
                    return { message: resultMessage, color: '#ff0000' };
                }
            },
            {
                emoji: '2️⃣',
                text: 'Fight with fists',
                async result(interaction, inventory) {
                    const outcome = Math.random();
                    let resultMessage = "";
                    let color;
    
                    if (outcome <= 0.40) {
                        resultMessage = "Triv destroys you in combat!\n";
                        const resources = ['wood', 'stone', 'copper', 'gold'];
    
                        // Track resource losses
                        resources.forEach(resource => {
                            if (inventory[resource] > 0) {
                                inventory[resource] -= 1;
                                resultMessage += `-1 ${resourceEmojiMap[resource]}\n`;
                            }
                        });
                        color = '#ff0000';
                    } else if (outcome <= 0.60) {
                        resultMessage = "You and Triv exchange blows, resulting in a stalemate...";
                        color = '#ffff00';
                    } else {
                        resultMessage = "You disarm triv in battle and he flees, dropping resources!\n";
                        const resources = {
                            wood: [1, 3],
                            stone: [1, 3],
                            copper: [1, 3],
                            gold: [1, 3]
                        };
    
                        // Track resource gains
                        for (const [resource, range] of Object.entries(resources)) {
                            const gained = Math.floor(Math.random() * (range[1] - range[0] + 1)) + range[0];
                            inventory[resource] += gained;
                            resultMessage += `+${gained} ${resourceEmojiMap[resource]}\n`;
                        }
                        color = '#00ff00';
                    }
    
                    await inventory.save();
                    return { message: resultMessage, color };
                }
            },
            {
                emoji: '3️⃣',
                text: 'Fight with your Axe (🪓 -10 Durability)',
                async result(interaction, inventory, tools) {
                    // Check if the user has an axe and enough durability
                    if (!tools.metalAxe || tools.metalAxeDurability < 10) {
                        // User is defeated due to lack of durability
                        let resultMessage = "You fumble around and are swiftly defeated!\n";
                        const resources = ['wood', 'stone', 'copper', 'gold'];
                
                        // Track resource losses
                        resources.forEach(resource => {
                            if (inventory[resource] > 0) {
                                inventory[resource] -= 1;
                                resultMessage += `-1 ${resourceEmojiMap[resource]}\n`;
                            }
                        });
                        await inventory.save();
                        return { message: resultMessage, color: '#ff0000' };
                    }
                
                    // Deduct axe durability
                    tools.metalAxeDurability -= 10;
                    await tools.save();
                
                    let resultMessage = "Fight with your Axe (🪓 -10 Durability)\n";
                    const outcome = Math.random();
                    let color;
                
                    if (outcome <= 0.1) {
                        resultMessage += "Triv destroys you in combat!\n";
                        const resources = ['wood', 'stone', 'copper', 'gold'];
                
                        // Track resource losses
                        resources.forEach(resource => {
                            if (inventory[resource] > 0) {
                                inventory[resource] -= 1;
                                resultMessage += `-1 ${resourceEmojiMap[resource]}\n`;
                            }
                        });
                        color = '#ff0000';
                    } else if (outcome <= 0.25) {
                        resultMessage += "You and Triv exchange blows, resulting in a stalemate...";
                        color = '#ffff00';
                    } else {
                        resultMessage += "You slay Triv in battle! You gain a wealth of resources.\n";
                        const resources = {
                            wood: [5, 15],
                            palmLeaves: [5, 15],
                            stone: [5, 15],
                            copper: [5, 15],
                            gold: [5, 15]
                        };
                
                        // Track resource gains
                        for (const [resource, range] of Object.entries(resources)) {
                            const gained = Math.floor(Math.random() * (range[1] - range[0] + 1)) + range[0];
                            inventory[resource] += gained;
                            resultMessage += `+${gained} ${resourceEmojiMap[resource]}\n`;
                        }
                        if (Math.random() <= 0.25) { // 25% small chance for ruby
                            inventory.ruby += 1;
                            resultMessage += `+1♦️ \n`;
                        }
                        color = '#00ff00';
                    }
                
                    await inventory.save();
                    return { message: resultMessage, color };
                }
            }                  
        ]
    },
    {
        id: 7,
        description: "You encounter NF89, a blacksmith, who offers to craft tools or buy items.",
        imageUrl: "https://cdn.discordapp.com/attachments/704530416475832342/1274977215314133023/NFTHEBLACKSMITH.png?ex=66c43690&is=66c2e510&hm=8278fd5ea5fba7b55b544de5ab4a92043c1d68dd830ec432576f34a5510e3593&", // Use an appropriate image URL
        choices: [
            {
                emoji: '1️⃣',
                text: 'Craft Axe\n-25🪵 -50🪨 -50🔶 -10🪢 -10✨',
                async result(interaction, inventory, tools) {
                    // Check if the user has enough resources
                    if (inventory.wood < 25 || inventory.stone < 50 || inventory.copper < 50 || inventory.rope < 10 || inventory.gold < 10) {
                        let resultMessage = "You don’t have enough resources to craft an axe. NF89 shakes his head in disappointment.\n";
    
                        await inventory.save();
                        return { message: resultMessage, color: '#ff0000' };
                    }
    
                    // Deduct resources
                    inventory.wood -= 25;
                    inventory.stone -= 50;
                    inventory.copper -= 50;
                    inventory.rope -= 10;
                    inventory.gold -= 10;
    
                    // Check if user already has an axe and update durability or add a new one
                    if (tools.metalAxe) {
                        tools.metalAxeDurability = 50;
                    } else {
                        tools.metalAxe = true;
                        tools.metalAxeDurability = 50;
                    }
    
                    await tools.save();
                    await inventory.save();
    
                    let resultMessage = "NF89 crafts you a new axe 🪓!\n";
                    return { message: resultMessage, color: '#00ff00' };
                }
            },
            {
                emoji: '2️⃣',
                text: 'Craft Pickaxe\n-25🪵 -50🪨 -50🔶 -10🪢 -10✨',
                async result(interaction, inventory, tools) {
                    // Check if the user has enough resources
                    if (inventory.wood < 25 || inventory.stone < 50 || inventory.copper < 50 || inventory.rope < 10 || inventory.gold < 10) {
                        let resultMessage = "You don’t have enough resources to craft a pickaxe. NF89 shakes his head in disappointment.\n";
    
                        await inventory.save();
                        return { message: resultMessage, color: '#ff0000' };
                    }
    
                    // Deduct resources
                    inventory.wood -= 25;
                    inventory.stone -= 50;
                    inventory.copper -= 50;
                    inventory.rope -= 10;
                    inventory.gold -= 10;
    
                    // Check if user already has a pickaxe and update durability or add a new one
                    if (tools.metalPickaxe) {
                        tools.metalPickaxeDurability = 50;
                    } else {
                        tools.metalPickaxe = true;
                        tools.metalPickaxeDurability = 50;
                    }
    
                    await tools.save();
                    await inventory.save();
    
                    let resultMessage = "NF89 crafts you a new pickaxe ⛏️!\n";
                    return { message: resultMessage, color: '#00ff00' };
                }
            },
            {
                emoji: '3️⃣',
                text: 'Trade 50 🪨 for 1♦️',
                async result(interaction, inventory) {
                    // Check if the user has enough resources
                    if (inventory.stone < 50) {
                        let resultMessage = "You don’t have enough stone to trade. NF89 shakes his head in disappointment.\n";
    
                        await inventory.save();
                        return { message: resultMessage, color: '#ff0000' };
                    }
    
                    // Deduct resources and give ruby
                    inventory.stone -= 50;
                    inventory.ruby += 1;
    
                    await inventory.save();
    
                    let resultMessage = "NF89 trades you 1 ♦️ for 50 🪨!\n";
                    return { message: resultMessage, color: '#00ff00' };
                }
            },
            {
                emoji: '4️⃣',
                text: 'Leave',
                async result() {
                    let resultMessage = "You decide to leave NF89’s workshop and continue on your journey.\n";
                    return { message: resultMessage, color: '#ffff00' };
                }
            }
        ]
    }
];





























//------------------------------------------------
// HELPER FUNCTIONS:
//------------------------------------------------
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
            resultMessage += `**-${amount}** ${resource === 'wood' ? '🪵' : resource === 'stone' ? '🪨' : '🌿'}`;
            resourceFound = true;
        }

        if (resources.every(r => inventory[r] < 1)) {
            resultMessage = 'Dolphe gets mad but you don\'t have enough resources to lose.';
            resourceFound = true;
        }
    }

    return { message: resultMessage, color: '#ff0000' }; // Red color for Dolphe stealing
}

//------------------------------------------------
async function handleRockPurchase(interaction, inventory, quantity) {
    const woodCost = 6 * quantity;
    const stoneCost = 3 * quantity;

    if (inventory.wood < woodCost || inventory.stone < stoneCost) {
        return { message: `You don’t have enough resources to buy ${quantity} rock(s).`, color: '#ff0000' };
    }

    inventory.wood -= woodCost;
    inventory.stone -= stoneCost;
    await inventory.save();

    let resultMessage = `You bought ${quantity} rock(s) from Duko.\nOpening the rocks...\n`;
    for (let i = 0; i < quantity; i++) {
        const chance = Math.random() * 100;

        if (chance < 0.8) { // 0.8% chance to get 1💎
            inventory.diamond = (inventory.diamond || 0) + 1;
            resultMessage += '**《◊【༺LEGENDARY༻】◊》** You got 1 💎!\n';
        } else if (chance < 1.8) { // 1% chance to get 3-4♦️
            const rubyAmount = Math.floor(Math.random() * 2) + 3;
            inventory.ruby = (inventory.ruby || 0) + rubyAmount;
            resultMessage += `**《◊【༺LEGENDARY༻】◊》** You got ${rubyAmount} ♦️!\n`;
        } else if (chance < 5.5) { // 3.7% chance to get 1-2♦️
            const rubyAmount = Math.floor(Math.random() * 2) + 1;
            inventory.ruby = (inventory.ruby || 0) + rubyAmount;
            resultMessage += `**《【EPIC】》** You got ${rubyAmount} ♦️!\n`;
        } else if (chance < 10.0) { // 4.5% chance to get 4-7✨
            const goldAmount = Math.floor(Math.random() * 4) + 4;
            inventory.gold = (inventory.gold || 0) + goldAmount;
            resultMessage += `**《【EPIC】》** You got ${goldAmount} ✨!\n`;
        } else if (chance < 19.0) { // 9% chance to get 1-3✨
            const goldAmount = Math.floor(Math.random() * 3) + 1;
            inventory.gold = (inventory.gold || 0) + goldAmount;
            resultMessage += `**【RARE】** You got ${goldAmount} ✨!\n`;
        } else if (chance < 30.0) { // 11% chance to get 4-7🔶
            const copperAmount = Math.floor(Math.random() * 4) + 4;
            inventory.copper = (inventory.copper || 0) + copperAmount;
            resultMessage += `**【RARE】** You got ${copperAmount} 🔶!\n`;
        } else if (chance < 45.0) { // 15% chance to get 2-3🔶
            const copperAmount = Math.floor(Math.random() * 2) + 2;
            inventory.copper = (inventory.copper || 0) + copperAmount;
            resultMessage += `**〈UNCOMMON〉** You got ${copperAmount} 🔶!\n`;
        } else if (chance < 60.0) { // 15% chance to get 2-4🪨
            const stoneAmount = Math.floor(Math.random() * 3) + 2;
            inventory.stone = (inventory.stone || 0) + stoneAmount;
            resultMessage += `**〈UNCOMMON〉** You got ${stoneAmount} 🪨!\n`;
        } else if (chance < 80.0) { // 20% chance to get 1🪨
            inventory.stone = (inventory.stone || 0) + 1;
            resultMessage += '**COMMON** You got 1 🪨!\n';
        } else if (chance < 100.0) { // 20% chance to get 1🔶
            inventory.copper = (inventory.copper || 0) + 1;
            resultMessage += '**COMMON** You got 1 🔶!\n';
        }
    }

    await inventory.save();
    return { message: resultMessage, color: '#00ff00' };
}














//------------------------------------------------
// THE COMMAND
//------------------------------------------------

const activeExplores = new Set();

module.exports = {
    data: new SlashCommandBuilder()
        .setName('explore')
        .setDescription('Explore and make choices to gain or lose resources.'),
    
        async execute(interaction) {
            const userId = interaction.user.id;
        
            // Check if the user is already exploring
            if (activeExplores.has(userId)) {
                return interaction.reply({
                    content: 'You are already exploring! Please wait until your current exploration is finished.',
                    ephemeral: true
                });
            }
        
            // Find or create the user, inventory, and tools
            const [user] = await User.findOrCreate({ where: { discordId: userId } });
            const [inventory] = await Inventory.findOrCreate({ where: { userId: user.id } });
            const [tools] = await Tool.findOrCreate({ where: { userId: user.id } });
        
            // Cooldown check
            const now = Date.now();
            const cooldown = 30 * 1000; // 30 seconds
            const lastExplore = user.lastExplore || 0;
        
            if (now - lastExplore < cooldown) {
                const remainingTime = Math.ceil((cooldown - (now - lastExplore)) / 1000);
                return interaction.reply({ content: `Please wait ${remainingTime} seconds before exploring again.`, ephemeral: true });
            }
        
            // Add user to active explores set
            activeExplores.add(userId);
            
            try {
                // Update the lastExplore time
                user.lastExplore = now;
                await user.save();
        
                // Choose a random event
                const event = events[Math.floor(Math.random() * events.length)];
                console.log(`event ID: ${event.id}`);
                // Create an embed for the event
                const embed = new EmbedBuilder()
                    .setColor('#0099ff')
                    .setTitle('Exploration Event!')
                    .setThumbnail(interaction.user.displayAvatarURL()) // Add the user's avatar as a thumbnail
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
                    // Ensure tools is defined and passed correctly
                    if (tools) {
                        const { message: resultMessage, color: embedColor } = await choice.result(interaction, inventory, tools);
        
                        const resultEmbed = new EmbedBuilder()
                            .setColor(embedColor)
                            .setTitle('Event Result')
                            .setDescription(resultMessage)
                            .setImage(event.imageUrl);
        
                        activeExplores.delete(userId);
        
                        await message.edit({ embeds: [resultEmbed] });
        
                        collector.stop();
                    } else {
                        console.error('Tools not found for user:', userId);
                    }
                });
        
                collector.on('end', (collected, reason) => {
                    if (reason === 'time') {
                        const timeoutEmbed = new EmbedBuilder()
                            .setColor('#ff0000')
                            .setTitle('Timeout')
                            .setDescription('You did not react in time. Please use the command again.')
                            .setImage(event.imageUrl);
        
                        message.edit({ embeds: [timeoutEmbed] });
        
                        activeExplores.delete(userId);
                    }
                });
        
            } 
            catch (error) 
            {
                console.error('Error executing explore command:', error);
                activeExplores.delete(userId);
                return interaction.reply({ content: 'An error occurred while executing the command. Please try again later.', ephemeral: true });
            } 
        } 
};