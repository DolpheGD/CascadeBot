// sync database
const sequelize = require('../dbConfig'); // Adjust path if necessary
const User = require('../models/User'); // Adjust path if necessary

(async () => {
    try {
        console.log('Syncing database...');
        await sequelize.sync({ alter: true }); // This will update the database schema
        console.log('Database synchronized.');
    } catch (error) {
        console.error('Error syncing database:', error);
    }
})();
