import loadUsers from "./load-users";
import {useEffect, useState} from "react";
import MyButton from "../ui/Button";
import MyTable from "../ui/Table"
import {Box} from '@mantine/core'

interface User {
    id: number;
    name: string;
    email: string;
}


const UsersInfo = () => {
    const [users, setUsers] = useState<User[]>([]);
    const [isLoading, setIsLoading] = useState(false)

    async function handleLoadUsers() {
        setIsLoading(true);
        try {
            const users = await loadUsers();
            console.log(users);
            setUsers(users);
        } catch (error) {
            console.error('Failed to fetch Users', error)
        } finally {
            setIsLoading(false)
        }

    }

    useEffect(() => {
        handleLoadUsers();
    }, []);

    return (
        // Mantine Components ADD
        <Box className="dashboard-section">
            <MyButton
                label='Reload'
                onClick={handleLoadUsers}
                loading={isLoading}
            />
            <MyTable data={users}/>
        </Box>
    )
}

export default UsersInfo;