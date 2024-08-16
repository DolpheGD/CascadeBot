const { DataTypes } = require('sequelize');
const sequelize = require('../dbConfig'); // Adjust if necessary

const User = sequelize.define('User', {
    discordId: {
        type: DataTypes.STRING,
        unique: true,
    },
    wood: {
        type: DataTypes.INTEGER,
        defaultValue: 0,
    },
    stone: {
        type: DataTypes.INTEGER,
        defaultValue: 0,
    },
    lastChop: {
        type: DataTypes.BIGINT,
        defaultValue: 0,
    },
    lastMine: {
        type: DataTypes.BIGINT,
        defaultValue: 0,
    },
});


module.exports = User;