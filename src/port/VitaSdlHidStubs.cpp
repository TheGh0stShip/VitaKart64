#ifdef __vita__

extern "C" {

int VITA_InitKeyboard(void) {
    return 0;
}

int VITA_PollKeyboard(void) {
    return 0;
}

int VITA_InitMouse(void) {
    return 0;
}

int VITA_PollMouse(void) {
    return 0;
}

}

#endif
