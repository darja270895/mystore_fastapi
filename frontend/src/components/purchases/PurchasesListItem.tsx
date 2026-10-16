import type {Purchase} from './purchases.types';
import {Table} from '@mantine/core';

const PurchasesListItem = ({id, user_id, product_id, amount, created_at}: Purchase) => {
    return (
        <Table.Tr>
            <Table.Td>{id}</Table.Td>
            <Table.Td>{user_id}</Table.Td>
            <Table.Td>{product_id}</Table.Td>
            <Table.Td>{amount}</Table.Td>
            <Table.Td>{created_at ? new Date(created_at).toLocaleString() : '—'}</Table.Td>
        </Table.Tr>
    );
};

export default PurchasesListItem;
