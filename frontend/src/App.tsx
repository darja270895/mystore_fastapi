import './App.css'
import AppMain from './components/app-main/AppMain'
import {AppLayout} from "./components/ui/AppLayout";
import {TestComponent} from './components/TestComponent'
import {useState} from 'react'
import {useDisclosure} from '@mantine/hooks';

// const API = "http://127.0.0.1:8000"

// function WhoAmI({name, link}:


// Component. That's a JS function that returns markup.
function App() {




    return (
        <div>
            <AppLayout>
                {/*<TestComponent></TestComponent>*/}
                <AppMain/>


                {/*<WhoAmIFunct name={{firstname: 'Daria', surname: 'Harashchenia'}}*/}
                {/*             link="https://www.linkedin.com/in/daria-harashchenia-949081107/"/>*/}

            </AppLayout>
        </div>
    );
}



export default App;
