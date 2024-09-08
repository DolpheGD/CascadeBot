// src/jobs/autoJob.js
const cron = require('node-cron');
const AutoMachine = require('../models/AutoMachine');
const { Op } = require('sequelize');

// Schedule the job to run every hour
cron.schedule('0 * * * *', async () => {
    console.log('Running scheduled resource collection job...');

    try {
        const now = new Date();

        // Fetch all automachines
        const machines = await AutoMachine.findAll();
        
        for (const machine of machines) {
            const hoursElapsed = Math.floor((now - new Date(machine.lastCollected)) / (60 * 60 * 1000));

            if (hoursElapsed > 0) {
                let woodCollected = 0, ropeCollected = 0, stoneCollected = 0, copperCollected = 0;
                let palmLeavesCollected = 0, berriesCollected = 0, applesCollected = 0;

                // Check the type of machine and calculate resource collection
                if (machine.type === 'autochopper') {
                    woodCollected = Math.min(hoursElapsed * (10 + 2 * machine.upgradeLevel), 200 - machine.wood); // max at the end
                    ropeCollected = Math.min(hoursElapsed * (1 + machine.upgradeLevel), 10 - machine.rope);
                    machine.wood += woodCollected;
                    machine.rope += ropeCollected;
                } else if (machine.type === 'autominer') {
                    stoneCollected = Math.min(hoursElapsed * (10 + 2 * machine.upgradeLevel), 200 - machine.stone);
                    copperCollected = Math.min(hoursElapsed * (5 + 2 * machine.upgradeLevel), 100 - machine.copper);
                    machine.stone += stoneCollected;
                    machine.copper += copperCollected;
                } else if (machine.type === 'autoforager') {
                    palmLeavesCollected = Math.min(hoursElapsed * (5 + 2 * machine.upgradeLevel), 100 - machine.palmLeaves);
                    berriesCollected = Math.min(hoursElapsed * (5 + 2 * machine.upgradeLevel), 100 - machine.berries);
                    applesCollected = Math.min(hoursElapsed * (2 + machine.upgradeLevel), 20 - machine.apples);
                    machine.palmLeaves += palmLeavesCollected;
                    machine.berries += berriesCollected;
                    machine.apples += applesCollected;
                }

                // Update the machine's lastCollected timestamp and save the new resource values
                machine.lastCollected = now;
                await machine.save();

                console.log(`Updated ${machine.type} for user ${machine.userId}: Collected ${woodCollected} wood, ${ropeCollected} rope, ${stoneCollected} stone, ${copperCollected} copper, ${palmLeavesCollected} palm leaves, ${berriesCollected} berries, ${applesCollected} apples.`);
            }
        }

        console.log('Resource collection job completed successfully.');
    } catch (error) {
        console.error('Error running the scheduled job:', error);
    }
});
