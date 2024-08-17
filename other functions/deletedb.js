const path = require('node:path');
const fs = require('node:fs');
const { databasePath } = require('../dbConfig'); // Adjust the path if necessary

const deleteDatabase = () => {
    const dbFilePath = path.resolve(__dirname, '../database.sqlite');

    if (fs.existsSync(dbFilePath)) {
        fs.unlinkSync(dbFilePath);
        console.log('Database file deleted successfully.');
    } else {
        console.log('No database file found to delete.');
    }
};

deleteDatabase();
