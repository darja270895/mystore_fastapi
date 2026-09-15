import './App.css'
import AppMain from './components/app-main/AppMain'
import {useState} from 'react'
import {Modal, Button} from '@mantine/core'
import {useDisclosure} from '@mantine/hooks';

// const API = "http://127.0.0.1:8000"

// function WhoAmI({name, link}:

interface WhoAmIProps {
    name: { firstname: string; surname: string; };
    link: string;
}

function WhoAmIFunct({name, link}: WhoAmIProps) {
    const [years, setYears] = useState(27)
    const nextYear = () => {
        setYears(years + 1)
    }
    return (
        <>
            <button onClick={nextYear}>+++</button>
            <div className="bio-card-top-right">
                <h3 className="text-sm font-semibold text-gray-900">made
                    by {name.firstname} {name.surname}, {years} y.o.</h3>
                <a className="text-xs text-gray-500" href={link}>My linkedIn</a>
            </div>
        </>
    )
}

// Component. That's a JS function that returns markup.
function App() {
    const [opened, {open, close}] = useDisclosure(false)

    return (
        <div>
            <WhoAmIFunct name={{firstname: 'Daria', surname: 'Harashchenia'}}
                         link="https://www.linkedin.com/in/daria-harashchenia-949081107/"/>
            <AppMain/>
            <Modal opened={opened} onClose={close} centered></Modal>
            <Button variant="default" onClick={open}>
                Register
            </Button>
        </div>
    );
}

export default App;
