const sequelize = require('../dbConfig'); // Adjust the path if necessary


const syncDatabase = async () => {
    try {
        console.log('Starting database synchronization...');
        sequelize.sync({ alter: true })
        await sequelize.sync({ force: true }); // This will drop and recreate tables
        console.log('Database synchronization complete.');
    } catch (error) {
        console.error('Error during database synchronization:', error);
    }
};

syncDatabase();
