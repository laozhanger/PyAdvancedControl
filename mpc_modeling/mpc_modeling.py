#! /usr/bin/python
# -*- coding: utf-8 -*
"""
Model predictive control sample code without modeling tool (cvxpy)

author: Atsushi Sakai

"""

import cvxpy
import numpy as np
import matplotlib.pyplot as plt

import cvxopt
from cvxopt import matrix
import scipy.linalg

DEBUG_ = False


def use_modeling_tool(A, B, N, Q, R, P, x0, umax=None, umin=None, xmin=None, xmax=None):
    """
    solve MPC with modeling tool for test
    """
    (nx, nu) = B.shape

    # mpc calculation
    x = cvxpy.Variable(nx, N + 1)
    u = cvxpy.Variable(nu, N)

    costlist = 0.0
    constrlist = []

    for t in range(N):
        costlist += 0.5 * cvxpy.quad_form(x[:, t], Q)
        costlist += 0.5 * cvxpy.quad_form(u[:, t], R)

        constrlist += [x[:, t + 1] == A * x[:, t] + B * u[:, t]]

        if xmin is not None:
            constrlist += [x[:, t] >= xmin]
        if xmax is not None:
            constrlist += [x[:, t] <= xmax]

    costlist += 0.5 * cvxpy.quad_form(x[:, N], P)  # terminal cost
    if xmin is not None:
        constrlist += [x[:, N] >= xmin]
    if xmax is not None:
        constrlist += [x[:, N] <= xmax]

    prob = cvxpy.Problem(cvxpy.Minimize(costlist), constrlist)

    prob.constraints += [x[:, 0] == x0]  # inital state constraints
    if umax is not None:
        prob.constraints += [u <= umax]  # input constraints
    if umin is not None:
        prob.constraints += [u >= umin]  # input constraints

    prob.solve(verbose=True)

    return x.value, u.value


def opt_mpc_with_input_const(A, B, N, Q, R, P, x0, umax=None, umin=None):
    """
    optimize model predictive control only with input constraints
    (if you want to solve a problem with state constraints, you can use opt_mpc_with_state_const())

    return
        x: state
        u: state
    """
    (nx, nu) = B.shape

    # calc AA
    Ai = A
    AA = Ai
    for i in range(2, N + 1):
        Ai = A * Ai
        AA = np.vstack((AA, Ai))
    #  print(AA)

    # calc BB
    AiB = B
    BB = np.kron(np.eye(N), AiB)
    for i in range(1, N):
        AiB = A * AiB
        BB += np.kron(np.diag(np.ones(N - i), -i), AiB)
    #  print(BB)

    RR = np.kron(np.eye(N), R)
    QQ = scipy.linalg.block_diag(np.kron(np.eye(N - 1), Q), P)

    H = (BB.T * QQ * BB + RR)
    #  print(H)

    gx0 = BB.T * QQ * AA * x0
    #  print(gx0)
    P = matrix(H)
    q = matrix(gx0)

    if umax is None and umin is None:
        sol = cvxopt.solvers.qp(P, q)
        #  print(sol)
    else:
        G = np.zeros((0, nu * N))
        h = np.zeros((0, 1))

        if umax is not None:
            tG = np.eye(N * nu)
            th = np.kron(np.ones((N * nu, 1)), umax)
            G = np.vstack([G, tG])
            h = np.vstack([h, th])

        if umin is not None:
            tG = np.eye(N * nu) * -1.0
            th = np.kron(np.ones((N * nu, 1)), umin * -1.0)
            G = np.vstack([G, tG])
            h = np.vstack([h, th])

        G = matrix(G)
        h = matrix(h)

        sol = cvxopt.solvers.qp(P, q, G, h)

    u = np.matrix(sol["x"])

    # recover x
    xx = AA * x0 + BB * u
    x = np.vstack((x0.T, xx.reshape(N, nx)))

    return x, u


def generate_inequalities_constraints_mat(N, nx, nu, xmin, xmax, umin, umax):
    """
    generate matrices of inequalities constrints

    return G, h
    """
    G = np.zeros((0, (nx + nu) * N))
    h = np.zeros((0, 1))
    if umax is not None:
        tG = np.hstack([np.eye(N * nu), np.zeros((N * nu, nx * N))])
        th = np.kron(np.ones((N * nu, 1)), umax)
        G = np.vstack([G, tG])
        h = np.vstack([h, th])

    if umin is not None:
        tG = np.hstack([np.eye(N * nu) * -1.0, np.zeros((N * nu, nx * N))])
        th = np.kron(np.ones((N, 1)), umin * -1.0)
        G = np.vstack([G, tG])
        h = np.vstack([h, th])

    if xmax is not None:
        tG = np.hstack([np.zeros((N * nx, nu * N)), np.eye(N * nx)])
        th = np.kron(np.ones((N, 1)), xmax)
        G = np.vstack([G, tG])
        h = np.vstack([h, th])

    if xmin is not None:
        tG = np.hstack([np.zeros((N * nx, nu * N)), np.eye(N * nx) * -1.0])
        th = np.kron(np.ones((N, 1)), xmin * -1.0)
        G = np.vstack([G, tG])
        h = np.vstack([h, th])

    return G, h


def opt_mpc_with_state_constr(A, B, N, Q, R, P, x0, xmin=None, xmax=None, umax=None, umin=None):
    """
    optimize MPC problem with state and (or) input constraints

    return
        x: state
        u: input
    """
    (nx, nu) = B.shape

    H = scipy.linalg.block_diag(np.kron(np.eye(N), R), np.kron(np.eye(N - 1), Q), np.eye(P.shape[0]))
    #  print(H)

    # calc Ae
    Aeu = np.kron(np.eye(N), -B)
    #  print(Aeu)
    #  print(Aeu.shape)
    Aex = scipy.linalg.block_diag(np.eye((N - 1) * nx), P)
    Aex -= np.kron(np.diag([1.0] * (N - 1), k=-1), A)
    #  print(Aex)
    #  print(Aex.shape)
    Ae = np.hstack((Aeu, Aex))
    #  print(Ae.shape)

    # calc be
    be = np.vstack((A, np.zeros(((N - 1) * nx, nx)))) * x0
    #  print(be)

    # === optimization ===
    P = matrix(H)
    q = matrix(np.zeros((N * nx + N * nu, 1)))
    A = matrix(Ae)
    b = matrix(be)

    if umax is None and umin is None:
        sol = cvxopt.solvers.qp(P, q, A=A, b=b)
    else:
        G, h = generate_inequalities_constraints_mat(N, nx, nu, xmin, xmax, umin, umax)

        G = matrix(G)
        h = matrix(h)

        sol = cvxopt.solvers.qp(P, q, G, h, A=A, b=b)

    #  print(sol)
    fx = np.matrix(sol["x"])
    #  print(fx)

    u = fx[0:N * nu].reshape(N, nu).T

    x = fx[-N * nx:].reshape(N, nx).T
    x = np.hstack((x0, x))
    #  print(x)
    #  print(u)

    return x, u


def test1():
    print("start!!")
    A = np.matrix([[0.8, 1.0], [0, 0.9]])
    #  print(A)
    B = np.matrix([[-1.0], [2.0]])
    #  print(B)
    (nx, nu) = B.shape
    #  print(nx, nu)

    N = 10  # number of horizon
    Q = np.eye(nx)
    #  print(Q)
    R = np.eye(nu)
    #  print(R)
    P = np.eye(nx)
    #  print(P)
    #  umax = 0.7

    x0 = np.matrix([[1.0], [2.0]])  # init state

    x, u = use_modeling_tool(A, B, N, Q, R, P, x0)

    rx1 = np.array(x[0, :]).flatten()
    rx2 = np.array(x[1, :]).flatten()
    ru = np.array(u[0, :]).flatten()

    flg, ax = plt.subplots(1)
    plt.plot(rx1, label="x1")
    plt.plot(rx2, label="x2")
    plt.plot(ru, label="u")
    plt.legend()
    plt.grid(True)

    x, u = opt_mpc_with_input_const(A, B, N, Q, R, P, x0)
    x1 = np.array(x[:, 0]).flatten()
    x2 = np.array(x[:, 1]).flatten()
    u = np.array(u).flatten()

    #  flg, ax = plt.subplots(1)
    plt.plot(x1, '*r', label="x1")
    plt.plot(x2, '*b', label="x2")
    plt.plot(u, '*k', label="u")
    plt.legend()
    plt.grid(True)

    if DEBUG_:
        plt.show()

    test_output_check(rx1, rx2, ru, x1, x2, u)


def test2():
    print("start!!")
    A = np.matrix([[0.8, 1.0], [0, 0.9]])
    B = np.matrix([[-1.0], [2.0]])
    (nx, nu) = B.shape

    N = 10  # number of horizon
    Q = np.eye(nx)
    R = np.eye(nu)
    P = np.eye(nx)
    umax = 0.7
    umin = -0.7

    x0 = np.matrix([[1.0], [2.0]])  # init state

    x, u = use_modeling_tool(A, B, N, Q, R, P, x0, umax=umax, umin=umin)
    #  x, u = use_modeling_tool(A, B, N, Q, R, P, x0, umin=umin)

    rx1 = np.array(x[0, :]).flatten()
    rx2 = np.array(x[1, :]).flatten()
    ru = np.array(u[0, :]).flatten()

    flg, ax = plt.subplots(1)
    plt.plot(rx1, label="x1")
    plt.plot(rx2, label="x2")
    plt.plot(ru, label="u")
    plt.legend()
    plt.grid(True)

    x, u = opt_mpc_with_input_const(A, B, N, Q, R, P, x0, umax=umax, umin=umin)
    x1 = np.array(x[:, 0]).flatten()
    x2 = np.array(x[:, 1]).flatten()
    u = np.array(u).flatten()

    #  flg, ax = plt.subplots(1)
    plt.plot(x1, '*r', label="x1")
    plt.plot(x2, '*b', label="x2")
    plt.plot(u, '*k', label="u")
    plt.legend()
    plt.grid(True)

    if DEBUG_:
        plt.show()

    test_output_check(rx1, rx2, ru, x1, x2, u)


def test3():
    print("start!!")
    A = np.matrix([[0.8, 1.0], [0, 0.9]])
    B = np.matrix([[-1.0], [2.0]])
    (nx, nu) = B.shape

    N = 10  # number of horizon
    Q = np.eye(nx)
    R = np.eye(nu)
    P = np.eye(nx)
    umax = 0.7
    umin = -0.7

    x0 = np.matrix([[1.0], [2.0]])  # init state
    x, u = use_modeling_tool(A, B, N, Q, R, P, x0, umax=umax, umin=umin)

    rx1 = np.array(x[0, :]).flatten()
    rx2 = np.array(x[1, :]).flatten()
    ru = np.array(u[0, :]).flatten()

    flg, ax = plt.subplots(1)
    plt.plot(rx1, label="x1")
    plt.plot(rx2, label="x2")
    plt.plot(ru, label="u")
    plt.legend()
    plt.grid(True)

    x, u = opt_mpc_with_state_constr(A, B, N, Q, R, P, x0, umax=umax, umin=umin)
    x1 = np.array(x[0, :]).flatten()
    x2 = np.array(x[1, :]).flatten()
    u = np.array(u).flatten()

    #  flg, ax = plt.subplots(1)
    plt.plot(x1, '*r', label="x1")
    plt.plot(x2, '*b', label="x2")
    plt.plot(u, '*k', label="u")
    plt.legend()
    plt.grid(True)

    if DEBUG_:
        plt.show()

    test_output_check(rx1, rx2, ru, x1, x2, u)


def test4():
    print("start!!")
    A = np.matrix([[0.8, 1.0], [0, 0.9]])
    B = np.matrix([[-1.0], [2.0]])
    (nx, nu) = B.shape

    N = 10  # number of horizon
    Q = np.eye(nx)
    R = np.eye(nu)
    P = np.eye(nx)

    x0 = np.matrix([[1.0], [2.0]])  # init state

    x, u = use_modeling_tool(A, B, N, Q, R, P, x0)

    rx1 = np.array(x[0, :]).flatten()
    rx2 = np.array(x[1, :]).flatten()
    ru = np.array(u[0, :]).flatten()

    flg, ax = plt.subplots(1)
    plt.plot(rx1, label="x1")
    plt.plot(rx2, label="x2")
    plt.plot(ru, label="u")
    plt.legend()
    plt.grid(True)

    x, u = opt_mpc_with_state_constr(A, B, N, Q, R, P, x0)
    x1 = np.array(x[0, :]).flatten()
    x2 = np.array(x[1, :]).flatten()
    u = np.array(u).flatten()

    #  flg, ax = plt.subplots(1)
    plt.plot(x1, '*r', label="x1")
    plt.plot(x2, '*b', label="x2")
    plt.plot(u, '*k', label="u")
    plt.legend()
    plt.grid(True)

    test_output_check(rx1, rx2, ru, x1, x2, u)

    if DEBUG_:
        plt.show()


def test5():
    print("start!!")
    A = np.matrix([[0.8, 1.0], [0, 0.9]])
    B = np.matrix([[-1.0], [2.0]])
    (nx, nu) = B.shape

    N = 10  # number of horizon
    Q = np.eye(nx)
    R = np.eye(nu)
    P = np.eye(nx)

    x0 = np.matrix([[1.0], [2.0]])  # init state
    umax = 0.7

    x, u = use_modeling_tool(A, B, N, Q, R, P, x0, umax=umax)

    rx1 = np.array(x[0, :]).flatten()
    rx2 = np.array(x[1, :]).flatten()
    ru = np.array(u[0, :]).flatten()

    flg, ax = plt.subplots(1)
    plt.plot(rx1, label="x1")
    plt.plot(rx2, label="x2")
    plt.plot(ru, label="u")
    plt.legend()
    plt.grid(True)

    x, u = opt_mpc_with_state_constr(A, B, N, Q, R, P, x0, umax=umax)
    x1 = np.array(x[0, :]).flatten()
    x2 = np.array(x[1, :]).flatten()
    u = np.array(u).flatten()

    #  flg, ax = plt.subplots(1)
    plt.plot(x1, '*r', label="x1")
    plt.plot(x2, '*b', label="x2")
    plt.plot(u, '*k', label="u")
    plt.legend()
    plt.grid(True)

    test_output_check(rx1, rx2, ru, x1, x2, u)

    if DEBUG_:
        plt.show()


def test6():
    print("start!!")
    A = np.matrix([[0.8, 1.0], [0, 0.9]])
    B = np.matrix([[-1.0], [2.0]])
    (nx, nu) = B.shape

    N = 10  # number of horizon
    Q = np.eye(nx)
    R = np.eye(nu)
    P = np.eye(nx)

    x0 = np.matrix([[1.0], [2.0]])  # init state
    umax = 0.7
    umin = -0.7

    x0 = np.matrix([[1.0], [2.0]])  # init state

    xmin = np.matrix([[-3.5], [-0.5]])  # state constraints
    xmax = np.matrix([[3.5], [2.0]])  # state constraints

    x, u = use_modeling_tool(A, B, N, Q, R, P, x0, umax=umax, umin=umin, xmin=xmin, xmax=xmax)

    rx1 = np.array(x[0, :]).flatten()
    rx2 = np.array(x[1, :]).flatten()
    ru = np.array(u[0, :]).flatten()

    flg, ax = plt.subplots(1)
    plt.plot(rx1, label="x1")
    plt.plot(rx2, label="x2")
    plt.plot(ru, label="u")
    plt.legend()
    plt.grid(True)

    x, u = opt_mpc_with_state_constr(A, B, N, Q, R, P, x0, umax=umax, umin=umin, xmin=xmin, xmax=xmax)
    x1 = np.array(x[0, :]).flatten()
    x2 = np.array(x[1, :]).flatten()
    u = np.array(u).flatten()

    #  flg, ax = plt.subplots(1)
    plt.plot(x1, '*r', label="x1")
    plt.plot(x2, '*b', label="x2")
    plt.plot(u, '*k', label="u")
    plt.legend()
    plt.grid(True)

    if DEBUG_:
        plt.show()

    test_output_check(rx1, rx2, ru, x1, x2, u)


def test_output_check(rx1, rx2, ru, x1, x2, u):
    print("test x1")
    for (i, j) in zip(rx1, x1):
        print(i, j)
        assert (i - j) <= 0.0001, "Error"
    print("test x2")
    for (i, j) in zip(rx2, x2):
        print(i, j)
        assert (i - j) <= 0.0001, "Error"
    print("test u")
    for (i, j) in zip(ru, u):
        print(i, j)
        assert (i - j) <= 0.0001, "Error"


if __name__ == '__main__':
    DEBUG_ = True
    #  test1()
    test2()
    #  test3()
    #  test4()
    #  test5()
    #  test6()
