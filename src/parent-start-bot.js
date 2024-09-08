const { spawn } = require('child_process');

// Function to start the bot
function startBot() {
    // Spawn a new process to run the bot
    const botProcess = spawn('node', ['src/index.js'], { stdio: 'inherit' });

    // Listen for exit events
    botProcess.on('close', (code) => {
        if (code !== 0) {
            console.log(`Bot crashed with exit code ${code}. Restarting bot in 5 seconds...`);
            setTimeout(startBot, 5000); // Restart the bot after a 5 second delay
        } else {
            console.log("Bot stopped normally.");
        }
    });
}

// Start the bot for the first time
startBot();