import {
  CognitoUserPool,
  CognitoUser,
  AuthenticationDetails,
  CognitoUserAttribute,
  CognitoUserSession,
} from 'amazon-cognito-identity-js';

const userPool = new CognitoUserPool({
  UserPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID as string,
  ClientId: import.meta.env.VITE_COGNITO_CLIENT_ID as string,
});

function getCognitoUser(email: string): CognitoUser {
  return new CognitoUser({ Username: email, Pool: userPool });
}

export const authService = {
  signUp(email: string, password: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const attributes = [new CognitoUserAttribute({ Name: 'email', Value: email })];
      userPool.signUp(email, password, attributes, [], (err) => {
        if (err) return reject(err);
        resolve();
      });
    });
  },

  confirmSignUp(email: string, code: string): Promise<void> {
    return new Promise((resolve, reject) => {
      getCognitoUser(email).confirmRegistration(code, true, (err) => {
        if (err) return reject(err);
        resolve();
      });
    });
  },

  signIn(email: string, password: string): Promise<CognitoUserSession> {
    return new Promise((resolve, reject) => {
      const authDetails = new AuthenticationDetails({ Username: email, Password: password });
      getCognitoUser(email).authenticateUser(authDetails, {
        onSuccess: (session) => resolve(session),
        onFailure: (err) => reject(err),
      });
    });
  },

  signOut(): void {
    const user = userPool.getCurrentUser();
    if (user) user.signOut();
  },

  getSession(): Promise<CognitoUserSession | null> {
    return new Promise((resolve) => {
      const user = userPool.getCurrentUser();
      if (!user) return resolve(null);
      user.getSession((err: Error | null, session: CognitoUserSession | null) => {
        if (err || !session || !session.isValid()) return resolve(null);
        resolve(session);
      });
    });
  },

  async getIdToken(): Promise<string | null> {
    const session = await this.getSession();
    return session ? session.getIdToken().getJwtToken() : null;
  },
};
