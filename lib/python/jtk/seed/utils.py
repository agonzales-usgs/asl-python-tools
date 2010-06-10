def CMP_SEED_TIMES(A, B):
    for i in range(0, 7):
        if A[i] != B[i]:
            return A[i] - B[i]
    return 0
