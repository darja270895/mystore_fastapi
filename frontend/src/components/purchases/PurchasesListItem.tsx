import type {Purchase} from './purchases.types'

const PurchasesListItem = ({id, user_id, product_id, amount, date_value}: Purchase) => {
    return (
        <tr key={id}>
            <td>{id}</td>
            <td>{user_id}</td>
            <td>{product_id}</td>
            <td>{amount}</td>
            <td>{date_value}</td>
        </tr>


    )
}

export default PurchasesListItem;