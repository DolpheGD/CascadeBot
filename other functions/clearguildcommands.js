    // Clear guild commands
    
    try {
        console.log(`Clearing commands for guild ${guildId}...`);
        await rest.put(
            Routes.applicationGuildCommands(clientId, guildId),
            { body: [] },
        );
        console.log('Guild commands cleared.');
    } catch (error) {
        console.error(error);
    }