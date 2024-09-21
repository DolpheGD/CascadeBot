const { Model, DataTypes } = require('sequelize');
const sequelize = require('../dbConfig');

class Guild extends Model {}

Guild.init({
    userId: {
        type: DataTypes.INTEGER,
        allowNull: false,
        unique: true,
    },
    level: {
        type: DataTypes.INTEGER,
        defaultValue: 1,  // All guilds start at level 1
    }
}, {
    sequelize,
    modelName: 'Guild',
});

module.exports = Guild;