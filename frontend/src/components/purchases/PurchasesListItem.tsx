import type {Purchase} from './purchases.types'
import {Table} from '@mantine/core'

const PurchasesListItem = ({id, user_id, product_id, amount, date_value}: Purchase) => {
    return (
        <Table.Tr key={id}>
            <Table.Td>{id}</Table.Td>
            <Table.Td>{user_id}</Table.Td>
            <Table.Td>{product_id}</Table.Td>
            <Table.Td>{amount}</Table.Td>
            <Table.Td>{date_value}</Table.Td>
        </Table.Tr>


    )
}

export default PurchasesListItem;