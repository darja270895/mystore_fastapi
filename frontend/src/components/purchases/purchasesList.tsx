import PurchasesListItem from './PurchasesListItem';
import type {Purchase} from './purchases.types';
import {Box, Table} from '@mantine/core';

const PurchaseList = ({data}: {data: Purchase[]}) => {
    return (
        <Box className="dashboard-section">
            <h3>My purchases</h3>
            <Table>
                <Table.Thead>
                    <Table.Tr>
                        <Table.Th>ID</Table.Th>
                        <Table.Th>USER ID</Table.Th>
                        <Table.Th>PRODUCT ID</Table.Th>
                        <Table.Th>AMOUNT</Table.Th>
                        <Table.Th>DATE</Table.Th>
                    </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                    {data.map((item) => (
                        <PurchasesListItem key={item.id} {...item} />
                    ))}
                </Table.Tbody>
            </Table>
        </Box>
    );
};

export default PurchaseList;
