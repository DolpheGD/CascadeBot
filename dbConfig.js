const { Sequelize } = require('sequelize');

const sequelize = new Sequelize({
    dialect: 'sqlite',
    storage: 'database.sqlite',
    logging: false, // Disable logging to keep the console clean
});

module.exports = sequelize;
