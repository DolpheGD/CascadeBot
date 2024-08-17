const { Sequelize, DataTypes } = require('sequelize');
const sequelize = new Sequelize({
    dialect: 'sqlite',
    storage: 'database.sqlite',
    logging: false,
});

const TestModel = sequelize.define('TestModel', {
    name: {
        type: DataTypes.STRING,
        allowNull: false
    },
});

(async () => {
    try {
        await sequelize.authenticate();
        console.log('Connection has been established successfully.');
        await sequelize.sync();
        console.log('TestModel has been synchronized successfully.');
    } catch (error) {
        console.error('Unable to connect to the database:', error);
    }
})();
