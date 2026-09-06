import loadUsers from "./load-users";
import {useEffect, useState} from "react";
import '../../App.css'


interface User {
    id: number;
    name: string;
    email: string;
}


const UsersInfo = () => {
    const [users, setUsers] = useState<User[]>([]);

    async function handleLoadUsers() {
        const users = await loadUsers();
        console.log(users);
        setUsers(users);
    }

    useEffect(() => {
        handleLoadUsers();
    }, []);

    return (
        <section className="dashboard-section">
            <button className="button" onClick={handleLoadUsers}>
                Refresh
            </button>
            <table>
                <thead>
                <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Email</th>
                </tr>
                </thead>
                <tbody>
                {users.map((user) => (
                    <tr key={user.id}>
                        <td>{user.id}</td>
                        <td>{user.name}</td>
                        <td>{user.email}</td>
                    </tr>
                ))}
                </tbody>
            </table>
        </section>
    )
}

export default UsersInfo;