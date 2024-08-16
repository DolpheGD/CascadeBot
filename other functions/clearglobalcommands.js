
    // Clear global commands
    try {
        console.log('Clearing global commands...');
        await rest.put(
            Routes.applicationCommands(clientId),
            { body: [] },
        );
        console.log('Global commands cleared.');
    } catch (error) {
        console.error(error);
    }
