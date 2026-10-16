import {useQuery} from '@tanstack/react-query';
import {Box} from '@mantine/core';
import MyButton from '../ui/Button';
import MyTable from '../ui/Table';
import {fetchUsers} from '../../api/users';
import {queryKeys} from '../../api/queryKeys';

const UsersInfo = () => {
    const usersQuery = useQuery({
        queryKey: queryKeys.users,
        queryFn: fetchUsers,
    });

    const users = usersQuery.data ?? [];

    return (
        <Box className="dashboard-section">
            <MyButton
                label="Reload"
                onClick={() => void usersQuery.refetch()}
                loading={usersQuery.isFetching}
            />
            <MyTable data={users as unknown as Record<string, unknown>[]} />
        </Box>
    );
};

export default UsersInfo;
