; Trampoline for calls between code banks (used through cc65's #pragma wrapped-call).
; The compiler sets tmp4 = bank of the callee and ptr4 = its address, then calls _bank_call.
; It lives in the fixed bank, so it can swap the caller's bank out and back in safely.
; A and X are preserved into the callee and back out of it (they carry arguments and results).
.export _bank_call
.import _romBankMirror, _bank_shift_out
.importzp tmp4, ptr4

.segment "CODE"

.proc _bank_call
    pha                         ; caller's A
    phx                         ; caller's X
    lda _romBankMirror
    pha                         ; the bank we came from
    lda tmp4
    cmp _romBankMirror
    beq @in
    jsr _bank_shift_out
@in:
    tsx
    ldy $0102,x                 ; saved X
    lda $0103,x                 ; saved A
    phy
    plx
    jsr @go
    pha                         ; result A
    phx                         ; result X
    tsx
    lda $0103,x                 ; the bank we came from
    cmp _romBankMirror
    beq @out
    jsr _bank_shift_out
@out:
    plx
    pla
    ply                         ; drop the three saved bytes
    ply
    ply
    rts
@go:
    jmp (ptr4)
.endproc
