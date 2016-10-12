/* Holds the data for LDAP accounts, retrieved from the LDAP server. */
create table if not exists ldap_account (
    id integer not null primary key,

    /* LDAP account unique identifier */
    uniqueid varchar(128) not null,
    /* LDAP email/username */
    email varchar(255) not null collate nocase,
    /* LDAP state
     * If the semaphor entry is ldaped and this column is False, then
     * the account is under the control of the DMA
     * and it is fully locked on the semaphor side.
     */
    enabled boolean not null default true,

    unique(email) on conflict replace,
    unique(uniqueid)
);

/* Holds the data for Semaphor accounts. */
create table if not exists semaphor_account (
    ldap_account integer, /* references ldap_account.id */ 

    /* Semaphor account unique identifier, which is the hash id of the account */
    semaphor_guid varchar(52),
    /* auto-generated Semaphor password */
    password varchar(32),
    /* level2 secret in base64 format */
    L2 varchar(44),

    /* semaphor account lock state
     * 0=ldaped/unlocked, 1=full-locked, 2=ldap-locked
     * - unlocked: account is under control of the DMA and unlocked.
     * - full-locked: account is under control of the DMA and fully locked.
     * - ldap-locked: account not under control of DMA, the account
     * is locked and the DMA is waiting for the user to join ldap or change username.
     */
    lock_state integer not null,    

    unique(semaphor_guid) on conflict replace,
    constraint fk_ldap_account foreign key(ldap_account) references ldap_account(id),
    constraint state_values check (lock_state >= 0 and lock_state <= 2)
);
